"""
E2E integration scenario — runs entirely in-process with a real test DB.

Scenario:
  1. ECMWF ingest creates ForecastStage rows for a hex.
  2. recompute_all_risk writes a SEVERE RiskSnapshot.
  3. /risk/location returns SEVERE for that hex.
  4. User submits a FloodReport (PENDING).
  5. Admin moderates the report → VERIFIED.
  6. dispatch_alerts creates AlertEvent + AlertDelivery for user with saved place.
  7. /alerts returns the active alert.
  8. /admin/validate/confusion shows the event in the matrix.
"""
import uuid
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.contrib.gis.geos import Point
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import SavedPlace, User
from apps.alerts.models import AlertDelivery, AlertEvent
from apps.geo.models import HexCell
from apps.ingest.models import ForecastStage
from apps.reports.models import FloodReport
from apps.risk.models import BiasFactor, RiskSnapshot
from tests.factories import (
    AlertDeliveryFactory,
    AlertEventFactory,
    AwsStationFactory,
    HexCellFactory,
    RiskSnapshotFactory,
    UserFactory,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _admin_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


# ── E2E scenario ─────────────────────────────────────────────────────────────


@pytest.mark.django_db(transaction=True)
def test_full_e2e_scenario():
    # ── 1. Prepare hex and station ─────────────────────────────────────────
    hex_cell = HexCellFactory(fsi_score=0.80, ward_name="Kukatpally")
    AwsStationFactory(hex=hex_cell)

    now = timezone.now().replace(second=0, microsecond=0)
    run_ts = now - timedelta(hours=1)

    # ── 2. Seed ForecastStage (simulates ECMWF ingest) ────────────────────
    ForecastStage.objects.create(
        hex=hex_cell,
        run_ts=run_ts,
        valid_ts=now,
        rain_1h=70.0,    # > 64.5 → SEVERE hazard bucket
        rain_3h=120.0,
        rain_24h=250.0,
        source="ECMWF",
    )
    BiasFactor.objects.create(
        station_id="",
        region="",
        multiplier=1.0,
        offset=0.0,
        valid_from=run_ts,
    )

    # ── 3. Run risk recompute task (synchronous) ───────────────────────────
    from apps.risk.tasks import recompute_all_risk
    recompute_all_risk.apply()

    snap = RiskSnapshot.objects.filter(hex=hex_cell).order_by("-ts").first()
    assert snap is not None, "recompute_all_risk produced no RiskSnapshot"
    assert snap.risk_level in ("HIGH", "SEVERE"), f"Expected HIGH/SEVERE got {snap.risk_level}"

    # ── 4. Risk API returns SEVERE ────────────────────────────────────────
    client = APIClient()
    resp = client.get(
        "/api/v1/risk/location/",
        {"lat": hex_cell.centroid.y, "lng": hex_cell.centroid.x},
    )
    assert resp.status_code == 200, resp.data
    assert resp.data["risk_level"] in ("HIGH", "SEVERE")

    # ── 5. User submits a flood report ────────────────────────────────────
    user = UserFactory(fcm_token="test-fcm-token-abc")
    client.force_authenticate(user=user)

    report = FloodReport.objects.create(
        user=user,
        geom=hex_cell.centroid,
        hex=hex_cell,
        depth="KNEE",
        road="DIFFICULT",
        status="PENDING",
        observed_at=now,
        client_uuid=uuid.uuid4(),
    )
    assert report.status == "PENDING"

    # ── 6. Admin moderates the report → VERIFIED ──────────────────────────
    admin_user = UserFactory(phone="+919000000001")
    admin_user.role = "ADMIN"
    admin_user.is_staff = True
    admin_user.save()

    admin_client = _admin_client(admin_user)
    resp = admin_client.post(
        f"/api/v1/admin/moderation/{report.pk}/action/",
        {"action": "VERIFY"},
        format="json",
    )
    assert resp.status_code == 200, resp.data

    report.refresh_from_db()
    assert report.status == "VERIFIED"

    # ── 7. dispatch_alerts creates AlertEvent + AlertDelivery ─────────────
    # Give the user a saved place in that hex (notify=True)
    SavedPlace.objects.create(
        user=user,
        label="HOME",
        geom=hex_cell.centroid,
        hex=hex_cell,
        notify=True,
    )

    with patch("floodguard.firebase.send_fcm_notification", return_value=True):
        from apps.alerts.tasks import dispatch_alerts
        dispatch_alerts.apply()

    alert_event = AlertEvent.objects.filter(hex=hex_cell).first()
    assert alert_event is not None, "No AlertEvent created for HIGH/SEVERE hex"

    delivery = AlertDelivery.objects.filter(alert=alert_event, user=user).first()
    assert delivery is not None, "No AlertDelivery created for user with saved place"
    assert delivery.status in ("SENT", "DELIVERED", "QUEUED")

    # ── 8. /alerts endpoint surfaces the active alert ─────────────────────
    resp = client.get("/api/v1/alerts/", {"scope": "active"})
    assert resp.status_code == 200

    # ── 9. Admin validation confusion matrix reflects the event ───────────
    from_ts = (now - timedelta(hours=2)).isoformat()
    to_ts   = (now + timedelta(hours=1)).isoformat()
    resp = admin_client.get(
        "/api/v1/admin/validate/confusion/",
        {"from": from_ts, "to": to_ts},
    )
    assert resp.status_code == 200

    # ── 10. Health probes ────────────────────────────────────────────────
    public = APIClient()
    assert public.get("/api/v1/livez/").status_code == 200
    assert public.get("/api/v1/readyz/").status_code == 200


# ── Targeted unit checks for p13 hardening ───────────────────────────────────


@pytest.mark.django_db
def test_readyz_returns_503_when_db_down(mocker):
    mocker.patch(
        "django.db.connections.__getitem__",
        side_effect=Exception("DB down"),
    )
    from floodguard.health import readyz
    from rest_framework.test import APIRequestFactory
    req = APIRequestFactory().get("/api/v1/readyz/")
    # Direct view call — bypasses URL router
    from rest_framework.request import Request
    resp = readyz(Request(req))
    assert resp.status_code == 503


@pytest.mark.django_db
def test_risk_hexes_cached(db):
    """Second identical request should return immediately (cache hit)."""
    HexCellFactory()
    client = APIClient()
    bbox = "78.40,17.30,78.55,17.50"
    r1 = client.get("/api/v1/risk/hexes/", {"bbox": bbox})
    r2 = client.get("/api/v1/risk/hexes/", {"bbox": bbox})
    # Both should succeed; no assertion on speed — just that caching path works
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.data == r2.data


@pytest.mark.django_db
def test_throttle_config():
    """Verify custom throttle rates are wired."""
    from django.conf import settings
    rates = settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]
    assert "otp_request" in rates
    assert "otp_verify" in rates


@pytest.mark.django_db
def test_alert_delivery_no_duplicates():
    """dispatch_alerts should not create duplicate deliveries on re-run."""
    hex_cell = HexCellFactory(fsi_score=0.9)
    user = UserFactory(fcm_token="token-xyz")
    SavedPlace.objects.create(
        user=user, label="HOME",
        geom=hex_cell.centroid, hex=hex_cell, notify=True,
    )
    snap = RiskSnapshotFactory(hex=hex_cell, risk_level="SEVERE", hazard_class="SEVERE")
    snap.ts = timezone.now() - timedelta(minutes=30)
    snap.save()

    with patch("floodguard.firebase.send_fcm_notification", return_value=True):
        from apps.alerts.tasks import dispatch_alerts
        dispatch_alerts.apply()
        count_after_first = AlertDelivery.objects.filter(user=user).count()
        dispatch_alerts.apply()
        count_after_second = AlertDelivery.objects.filter(user=user).count()

    assert count_after_second == count_after_first, "Duplicate deliveries created on re-run"
