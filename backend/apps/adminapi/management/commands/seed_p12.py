"""seed_p12 — Phase 12 DoD fixtures: analytics data, stale feed, pending reports."""
import uuid
from datetime import timedelta

from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = "Seed Phase 12 fixtures for DoD verification."

    def handle(self, *args, **options):
        from apps.accounts.models import User
        from apps.alerts.models import AlertDelivery, AlertEvent
        from apps.geo.models import HexCell
        from apps.ingest.models import IngestLog, RadarFrame
        from apps.reports.models import FloodReport
        from apps.risk.models import FsiWeights

        now = timezone.now().replace(minute=0, second=0, microsecond=0)

        # ── FsiWeights default row ────────────────────────────────────────────
        if not FsiWeights.objects.exists():
            FsiWeights.objects.create(updated_by="seed_p12")
            self.stdout.write("  FsiWeights default row created")

        # ── IngestLog — one stale feed (ecmwf last_success = 3 h ago) ────────
        for feed, delta_h, ok in [
            ("ecmwf",  3, False),  # stale — should be flagged red
            ("aws",    1, True),
            ("radar",  0, True),
        ]:
            log, _ = IngestLog.objects.get_or_create(feed=feed)
            log.last_success   = now - timedelta(hours=delta_h)
            log.last_attempted = now - timedelta(hours=delta_h)
            log.last_error     = "Connection timeout" if not ok else ""
            log.records_written = 0 if not ok else 120
            log.save()
        self.stdout.write("  IngestLog: ecmwf=stale, aws=ok, radar=ok")

        # ── RadarFrame entries ────────────────────────────────────────────────
        for h in range(6):
            ts = now - timedelta(hours=h)
            RadarFrame.objects.get_or_create(ts=ts, defaults={
                "tile_url_template": f"https://tiles.example.com/radar/{int(ts.timestamp())}/{{z}}/{{x}}/{{y}}.png",
                "anomaly": h == 2,
            })
        self.stdout.write("  6 RadarFrames (1 anomaly)")

        # ── Hex + AlertEvent + AlertDelivery (analytics) ─────────────────────
        hex_, _ = HexCell.objects.get_or_create(
            h3_index="891f4b1c3bfffff",
            defaults={"centroid": Point(78.45, 17.45), "ward_name": "Kondapur"},
        )

        viewer, _ = User.objects.get_or_create(
            phone="+910000000003",
            defaults={"is_staff": True, "role": "VIEWER"},
        )

        for i in range(5):
            event, _ = AlertEvent.objects.get_or_create(
                hex=hex_,
                window_start=now - timedelta(days=i),
                defaults={
                    "risk_level": ["HIGH", "MODERATE", "HIGH", "SEVERE", "MODERATE"][i],
                    "window_end": now - timedelta(days=i) + timedelta(hours=3),
                    "message": f"Test alert {i}",
                },
            )
            AlertDelivery.objects.get_or_create(
                alert=event, user=viewer,
                defaults={
                    "status": "DELIVERED" if i < 4 else "FAILED",
                    "sent_at": now - timedelta(days=i),
                    "delivered_at": now - timedelta(days=i) if i < 4 else None,
                },
            )
        self.stdout.write("  5 AlertEvents + deliveries")

        # ── Pending FloodReport for moderation queue ──────────────────────────
        FloodReport.objects.get_or_create(
            client_uuid=uuid.uuid5(uuid.NAMESPACE_OID, "p12_pending_001"),
            defaults={
                "geom":        Point(78.45, 17.45),
                "hex":         hex_,
                "depth":       "KNEE",
                "road":        "BLOCKED",
                "status":      "PENDING",
                "observed_at": now - timedelta(hours=1),
            },
        )
        FloodReport.objects.get_or_create(
            client_uuid=uuid.uuid5(uuid.NAMESPACE_OID, "p12_pending_002"),
            defaults={
                "geom":        Point(78.451, 17.451),
                "hex":         hex_,
                "depth":       "ANKLE",
                "road":        "DIFFICULT",
                "status":      "PENDING",
                "observed_at": now - timedelta(minutes=50),
            },
        )
        self.stdout.write("  2 PENDING reports (1 duplicate pair)")

        self.stdout.write(self.style.SUCCESS("Phase 12 fixtures ready."))
