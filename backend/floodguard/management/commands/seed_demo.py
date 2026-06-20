"""
seed_demo — populate the DB with enough synthetic data to make the app
            look alive in development (risk hex choropleth + radar frames).

Usage:
    python manage.py seed_demo          # idempotent; safe to re-run
    python manage.py seed_demo --clear  # wipe existing demo data first
"""
import random
from datetime import timedelta

from django.contrib.gis.geos import Point, Polygon
from django.core.management.base import BaseCommand
from django.utils import timezone

# Hyderabad centre
_HYD_LAT = 17.3850
_HYD_LNG = 78.4867

# Rough hex edge length at H3 res 9 ≈ 0.0016°
_HEX_HALF = 0.0009

RISK_LEVELS = ["LOW", "LOW", "MODERATE", "MODERATE", "HIGH", "SEVERE"]
WARD_NAMES = [
    "Kondapur", "Gachibowli", "Kukatpally", "Madhapur", "Hitech City",
    "Banjara Hills", "Jubilee Hills", "Ameerpet", "Begumpet", "Secunderabad",
    "LB Nagar", "Uppal", "Dilsukhnagar", "Vanasthalipuram", "Hayathnagar",
    "Mehdipatnam", "Tolichowki", "Attapur", "Rajendranagar", "Shamshabad",
    "Bowenpally", "Malkajgiri", "Sainikpuri", "Nagole", "Amberpet",
    "Nacharam", "Kushaiguda", "Yapral", "AS Rao Nagar", "ECIL",
]

# Synthetic H3-like indices (real res-9 format: 8 9 1 f 4 b ...)
_H3_PREFIX = "891f4b"


def _fake_h3(i: int) -> str:
    return f"{_H3_PREFIX}{i:06x}ff"


def _hex_polygon(lat: float, lng: float) -> Polygon:
    h = _HEX_HALF
    return Polygon((
        (lng - h, lat - h), (lng + h, lat - h),
        (lng + h, lat + h), (lng - h, lat + h),
        (lng - h, lat - h),
    ), srid=4326)


class Command(BaseCommand):
    help = "Seed demo HexCells + RiskSnapshots for local development."

    def add_arguments(self, parser):
        parser.add_argument("--clear", action="store_true",
                            help="Delete existing demo data before seeding.")
        parser.add_argument("--hexes", type=int, default=30,
                            help="Number of hex cells to create (default 30).")

    def handle(self, *args, **options):
        from apps.geo.models import HexCell
        from apps.ingest.models import RadarFrame
        from apps.ingest.parsers import radar as radar_parser
        from apps.risk.models import RiskSnapshot

        n_hexes = options["hexes"]

        if options["clear"]:
            HexCell.objects.filter(h3_index__startswith=_H3_PREFIX).delete()
            self.stdout.write("  cleared existing demo data")

        now = timezone.now().replace(second=0, microsecond=0)
        rng = random.Random(42)

        # ── 1. HexCells spread around Hyderabad ──────────────────────────────
        hex_cells = []
        lat_spread = 0.25
        lng_spread = 0.30

        for i in range(n_hexes):
            lat = _HYD_LAT + rng.uniform(-lat_spread, lat_spread)
            lng = _HYD_LNG + rng.uniform(-lng_spread, lng_spread)
            ward = WARD_NAMES[i % len(WARD_NAMES)]
            fsi = round(rng.uniform(0.2, 0.95), 3)

            cell, created = HexCell.objects.get_or_create(
                h3_index=_fake_h3(i),
                defaults={
                    "geom": _hex_polygon(lat, lng),
                    "centroid": Point(lng, lat, srid=4326),
                    "fsi_score": fsi,
                    "ward_name": ward,
                    "fsi_inputs": {
                        "twi": round(rng.uniform(0.1, 1.0), 2),
                        "depression_depth": round(rng.uniform(0.1, 1.0), 2),
                        "hand": round(rng.uniform(0.1, 1.0), 2),
                        "dist_to_water": round(rng.uniform(0.1, 1.0), 2),
                        "slope": round(rng.uniform(0.1, 0.6), 2),
                        "imperviousness": round(rng.uniform(0.3, 0.9), 2),
                    },
                },
            )
            hex_cells.append(cell)
            if created:
                self.stdout.write(f"  hex {cell.h3_index}  {ward}")

        self.stdout.write(self.style.SUCCESS(f"  {len(hex_cells)} hex cells ready"))

        # ── 2. RiskSnapshots — current ts + last 24 hourly frames ────────────
        snapshots_created = 0
        for h in range(25):
            ts = now - timedelta(hours=h)
            for cell in hex_cells:
                risk = rng.choice(RISK_LEVELS)
                # High-FSI hexes lean toward higher risk
                if cell.fsi_score > 0.7 and rng.random() < 0.5:
                    risk = rng.choice(["HIGH", "SEVERE"])
                hazard = risk  # simplified: hazard == risk for demo

                RiskSnapshot.objects.get_or_create(
                    hex=cell,
                    ts=ts,
                    defaults={
                        "rain_1h": round(rng.uniform(0, 70), 1),
                        "rain_3h": round(rng.uniform(0, 120), 1),
                        "rain_24h": round(rng.uniform(0, 250), 1),
                        "hazard_class": hazard,
                        "risk_level": risk,
                        "confidence": rng.randint(55, 95),
                        "source_model": "DEMO",
                    },
                )
                snapshots_created += 1

        self.stdout.write(self.style.SUCCESS(
            f"  {snapshots_created} RiskSnapshot rows ready (25 timestamps × {len(hex_cells)} hexes)"
        ))

        # ── 3. RadarFrames — last 12 frames from RainViewer ──────────────────
        radar_created = 0
        for m in range(0, 120, 10):   # 12 frames, 10-min apart
            ts = now - timedelta(minutes=m)
            frame = radar_parser.fetch_and_parse(
                ts, mock=True, api_url="", api_key=""
            )
            if frame:
                _, created = RadarFrame.objects.get_or_create(
                    ts=frame["ts"],
                    defaults={
                        "tile_url_template": frame["tile_url_template"],
                        "dbz_min": frame["dbz_min"],
                        "dbz_max": frame["dbz_max"],
                        "georef_ok": frame["georef_ok"],
                        "anomaly": frame["anomaly"],
                    },
                )
                if created:
                    radar_created += 1

        self.stdout.write(self.style.SUCCESS(f"  {radar_created} RadarFrame rows created"))
        self.stdout.write(self.style.SUCCESS("seed_demo done — restart the dev server if caching is on"))
