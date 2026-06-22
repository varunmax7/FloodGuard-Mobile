"""
alerts/tasks.py — dispatch_alerts Celery task.

Runs after risk recompute. For every hex that just entered HIGH/SEVERE:
  1. Create AlertEvent (idempotent — one per hex per risk level per hour)
  2. Find users with saved places (notify=True) in those hexes
  3. Send FCM push notification
  4. Record AlertDelivery with sent/delivered status
"""
import logging
from datetime import timedelta

from celery import shared_task
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger("floodguard.alerts")

_ALERT_LEVELS = {"HIGH", "SEVERE"}

_DEPTH_TO_RISK = {
    "ANKLE": "MODERATE",
    "KNEE": "HIGH",
    "WAIST": "SEVERE",
    "VEHICLE": "SEVERE",
}

_DEPTH_LABELS = {
    "ANKLE": "Ankle deep",
    "KNEE": "Knee deep",
    "WAIST": "Waist deep",
    "VEHICLE": "Vehicle level",
}

_ROAD_LABELS = {
    "PASSABLE": "road passable",
    "DIFFICULT": "road difficult",
    "BLOCKED": "road blocked",
}


def _build_message(risk_level: str, ward_name: str) -> str:
    area = ward_name or "Your area"
    phrases = {
        "HIGH":   f"High flood risk in {area}. Avoid low-lying roads.",
        "SEVERE": f"Severe flood risk in {area}. Stay indoors and avoid travel.",
    }
    return phrases.get(risk_level, f"Flood alert for {area}.")


@shared_task(
    bind=True,
    name="apps.alerts.tasks.dispatch_alerts",
    max_retries=2,
    default_retry_delay=60,
)
def dispatch_alerts(self):
    """Dispatch push alerts for hexes that entered HIGH/SEVERE in the last 2 h."""
    from apps.accounts.models import SavedPlace, User
    from apps.alerts.models import AlertDelivery, AlertEvent
    from apps.risk.models import RiskSnapshot
    from floodguard.firebase import send_fcm_notification

    try:
        now = timezone.now()
        lookback = now - timedelta(hours=2)
        alert_window = timedelta(hours=1)

        # Latest HIGH/SEVERE snapshots within the lookback window
        snapshots = (
            RiskSnapshot.objects
            .filter(risk_level__in=_ALERT_LEVELS, ts__gte=lookback)
            .select_related("hex")
            .order_by("hex_id", "-ts")
        )

        # Deduplicate to one snapshot per hex (latest)
        seen: set[str] = set()
        unique_snapshots = []
        for snap in snapshots:
            if snap.hex_id not in seen:
                seen.add(snap.hex_id)
                unique_snapshots.append(snap)

        dispatched = 0

        for snapshot in unique_snapshots:
            hex_cell = snapshot.hex
            ward = hex_cell.ward_name or ""

            # Idempotency: skip if an alert for this hex+level already exists this window
            recent_alert = AlertEvent.objects.filter(
                hex=hex_cell,
                risk_level=snapshot.risk_level,
                window_start__gte=now - alert_window,
            ).first()
            if recent_alert:
                continue

            message = _build_message(snapshot.risk_level, ward)

            with transaction.atomic():
                alert = AlertEvent.objects.create(
                    hex=hex_cell,
                    risk_level=snapshot.risk_level,
                    window_start=now,
                    window_end=now + alert_window,
                    message=message,
                )

            # Find users to notify
            users = User.objects.filter(
                saved_places__hex=hex_cell,
                saved_places__notify=True,
            ).exclude(fcm_token="").distinct()

            for user in users:
                delivery, _ = AlertDelivery.objects.get_or_create(
                    alert=alert,
                    user=user,
                    defaults={"status": "QUEUED"},
                )

                try:
                    title = f"⚠️ Flood Alert — {ward or 'Your area'}"
                    msg_id = send_fcm_notification(
                        token=user.fcm_token,
                        title=title,
                        body=message,
                        data={
                            "h3_index": hex_cell.h3_index,
                            "risk_level": snapshot.risk_level,
                            "alert_id": str(alert.id),
                        },
                    )
                    delivery.status = "DELIVERED" if msg_id else "SENT"
                    delivery.sent_at = now
                    if msg_id:
                        delivery.delivered_at = now
                    delivery.save(update_fields=["status", "sent_at", "delivered_at"])
                    dispatched += 1
                except Exception as exc:  # noqa: BLE001
                    logger.error("FCM send failed user=%s: %s", user.id, exc)
                    delivery.status = "FAILED"
                    delivery.save(update_fields=["status"])

        logger.info("dispatch_alerts: %d notifications sent", dispatched)
        return dispatched

    except Exception as exc:
        logger.exception("dispatch_alerts failed")
        raise self.retry(exc=exc)


@shared_task(
    bind=True,
    name="apps.alerts.tasks.dispatch_report_alert",
    max_retries=2,
    default_retry_delay=30,
)
def dispatch_report_alert(self, report_id: str):
    """
    Called immediately after an admin verifies a flood report.
    Notifies users with saved places within a 2-ring H3 radius (~500 m)
    of the report location, including the photo, depth, and road status.
    """
    import h3
    from apps.accounts.models import SavedPlace, User
    from apps.alerts.models import AlertDelivery, AlertEvent
    from apps.reports.models import FloodReport
    from floodguard.firebase import send_fcm_notification

    try:
        report = FloodReport.objects.select_related("hex").get(pk=report_id)

        if not report.hex:
            logger.warning("dispatch_report_alert: report %s has no hex, skipping", report_id)
            return 0

        risk_level = _DEPTH_TO_RISK.get(report.depth, "HIGH")
        ward = report.hex.ward_name or "Nearby area"
        depth_label = _DEPTH_LABELS.get(report.depth, report.depth.lower())
        road_label = _ROAD_LABELS.get(report.road, report.road.lower())

        message = (
            f"Flood reported near {ward}: {depth_label}, {road_label}. "
            "Verified by FloodGuard team."
        )

        now = timezone.now()
        window_end = now + timedelta(hours=6)

        alert = AlertEvent.objects.create(
            hex=report.hex,
            risk_level=risk_level,
            source="REPORT",
            report=report,
            window_start=now,
            window_end=window_end,
            message=message,
        )

        # Expand to k=2 ring (~500 m) to notify neighbours
        nearby_hex_ids = h3.grid_disk(report.hex.h3_index, 2)

        users = User.objects.filter(
            saved_places__hex_id__in=nearby_hex_ids,
            saved_places__notify=True,
        ).exclude(fcm_token="").distinct()

        dispatched = 0
        title = f"Flood Report Verified — {ward}"

        for user in users:
            delivery, _ = AlertDelivery.objects.get_or_create(
                alert=alert,
                user=user,
                defaults={"status": "QUEUED"},
            )
            try:
                msg_id = send_fcm_notification(
                    token=user.fcm_token,
                    title=title,
                    body=message,
                    data={
                        "alert_id": str(alert.id),
                        "source": "REPORT",
                        "h3_index": report.hex.h3_index,
                        "risk_level": risk_level,
                        "photo_url": report.photo_url or "",
                        "depth": report.depth,
                        "road": report.road,
                        "lat": str(report.geom.y),
                        "lon": str(report.geom.x),
                    },
                )
                delivery.status = "DELIVERED" if msg_id else "SENT"
                delivery.sent_at = now
                if msg_id:
                    delivery.delivered_at = now
                delivery.save(update_fields=["status", "sent_at", "delivered_at"])
                dispatched += 1
            except Exception as exc:  # noqa: BLE001
                logger.error("FCM send failed user=%s: %s", user.id, exc)
                delivery.status = "FAILED"
                delivery.save(update_fields=["status"])

        logger.info("dispatch_report_alert: report=%s dispatched=%d", report_id, dispatched)
        return dispatched

    except FloodReport.DoesNotExist:
        logger.error("dispatch_report_alert: report %s not found", report_id)
        return 0
    except Exception as exc:
        logger.exception("dispatch_report_alert failed")
        raise self.retry(exc=exc)
