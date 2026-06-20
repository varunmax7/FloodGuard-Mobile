"""seed_p11 — create Phase 11 test fixtures for DoD verification."""
import uuid
from datetime import timedelta

from django.contrib.gis.geos import Point, Polygon
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = "Seed Phase 11 fixtures: AWS station, forecasts, risk snapshots, flood reports."

    def handle(self, *args, **options):
        from apps.geo.models import AwsStation, AwsObservation, HexCell
        from apps.ingest.models import ForecastStage
        from apps.reports.models import FloodReport
        from apps.risk.models import BiasFactor, RiskSnapshot

        now = timezone.now().replace(minute=0, second=0, microsecond=0)

        # 1. HexCell
        hex_, _ = HexCell.objects.get_or_create(
            h3_index="891f4b1c3bfffff",
            defaults={
                "geom":      Polygon.from_bbox((78.40, 17.40, 78.50, 17.50)),
                "centroid":  Point(78.45, 17.45),
                "fsi_score": 0.72,
                "ward_name": "Kondapur",
            },
        )
        self.stdout.write(f"  hex {hex_.h3_index}")

        # 2. AWS Station
        station, _ = AwsStation.objects.get_or_create(
            station_id="AWS_P11",
            defaults={"name": "Kondapur Test Station", "geom": Point(78.45, 17.45), "hex": hex_},
        )
        self.stdout.write(f"  station {station.station_id}")

        # 3. Observed readings (72 h, hourly)
        for h in range(72):
            ts = now - timedelta(hours=h)
            AwsObservation.objects.get_or_create(
                station=station, ts=ts,
                defaults={
                    "rain_1h":  round(3.5 + (h % 7) * 0.8, 2),
                    "rain_3h":  round(9.0 + (h % 5) * 1.2, 2),
                    "rain_24h": round(28.0 + (h % 10) * 2.0, 2),
                },
            )

        # 4. ECMWF forecasts (slightly higher — positive bias)
        for h in range(72):
            ts = now - timedelta(hours=h)
            ForecastStage.objects.get_or_create(
                hex=hex_, valid_ts=ts, run_ts=ts, source="ECMWF",
                defaults={
                    "rain_1h":  round(4.2 + (h % 7) * 0.9, 2),
                    "rain_3h":  round(10.5 + (h % 5) * 1.3, 2),
                    "rain_24h": round(31.0 + (h % 10) * 2.1, 2),
                },
            )

        # 5. Risk snapshots (HIGH first 24 h, MODERATE rest)
        for h in range(72):
            ts    = now - timedelta(hours=h)
            level = "HIGH" if h < 24 else "MODERATE"
            RiskSnapshot.objects.get_or_create(
                hex=hex_, ts=ts,
                defaults={
                    "rain_1h": 4.2, "rain_3h": 10.5, "rain_24h": 31.0,
                    "hazard_class": level, "risk_level": level, "confidence": 80,
                },
            )

        # 6. Bias factor
        BiasFactor.objects.get_or_create(
            station_id="AWS_P11", valid_from=now - timedelta(days=7),
            defaults={"multiplier": 1.15, "offset": 0.5},
        )

        # 7. Flood reports for confusion matrix
        fixtures = [
            ("VERIFIED", "KNEE",  now - timedelta(hours=2)),   # HIGH predicted → agree
            ("VERIFIED", "ANKLE", now - timedelta(hours=5)),   # HIGH predicted → agree
            ("REJECTED", "ANKLE", now - timedelta(hours=30)),  # MODERATE predicted → agree
            ("REJECTED", "ANKLE", now - timedelta(hours=48)),  # MODERATE predicted → agree
        ]
        for status, depth, obs_at in fixtures:
            seed_key = f"p11_{status}_{depth}_{int(obs_at.timestamp())}"
            FloodReport.objects.get_or_create(
                client_uuid=uuid.uuid5(uuid.NAMESPACE_OID, seed_key),
                defaults={
                    "geom":        Point(78.45, 17.45),
                    "hex":         hex_,
                    "depth":       depth,
                    "road":        "DIFFICULT",
                    "status":      status,
                    "observed_at": obs_at,
                },
            )
        self.stdout.write(f"  {len(fixtures)} reports seeded")

        self.stdout.write(self.style.SUCCESS("Phase 11 fixtures ready."))
