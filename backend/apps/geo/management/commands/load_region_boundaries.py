"""
load_region_boundaries — ingest Telangana + Andhra Pradesh district and
sub-district (mandal) boundaries into the District / Taluka tables.

Region migration (2026-08-08)
-----------------------------
Replaces the older `load_assam_boundaries` command. The operating region is now
the union of two states — Telangana (33 districts) and Andhra Pradesh (26
districts) — treated as a single hexgrid / AWS grid / Nominatim viewport.

Source data
-----------
Survey of India / data.gov.in administrative boundary shapefiles:
    <source>/states/DISTRICT_BOUNDARY.shp        (all-India districts)
    <source>/talukas/SUBDISTRICT_BOUNDARY.shp    (all-India sub-districts)

Geometries are reprojected to EPSG:4326 using each layer's own .prj via GDAL.

Uniqueness
----------
District.name is not globally unique across states, so each District row is
tagged with its state ("Telangana" / "Andhra Pradesh") and unique-constrained
on (state, name).

Idempotent: upserts by (state, District.name) and by (district, Taluka.name);
safe to re-run. Fails loudly if a requested district has no boundary match.

Usage
-----
    manage.py load_region_boundaries --source ./boundaries --all
    manage.py load_region_boundaries --source ./boundaries --states Telangana
    manage.py load_region_boundaries --source ./boundaries --dry-run
"""
import logging
import re
from pathlib import Path

from django.contrib.gis.geos import MultiPolygon
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

logger = logging.getLogger("floodguard.geo")

# ── Target states ────────────────────────────────────────────────────────────
STATE_FIELD = "STATE_UT"
DIST_FIELD = "DISTRICT"
SUBDIST_FIELD = "SUB_DIST"

# Keys are normalized (uppercase, whitespace-collapsed) STATE_UT values.
# Values are the canonical state name written into District.state.
TARGET_STATES = {
    "TELANGANA": "Telangana",
    "ANDHRA PRADESH": "Andhra Pradesh",
    "ANDHRAPRADESH": "Andhra Pradesh",  # occasional joined-name variant
}

# ── Canonical district name resolution ───────────────────────────────────────
# Only entries for known variants / renames. Anything not in the map falls
# through to Title-case, e.g. "GUNTUR" -> "Guntur".
DISTRICT_VARIANT_MAP = {
    # Telangana
    "HANAMKONDA": "Hanumakonda",
    "HANUMAKONDA": "Hanumakonda",
    "WARANGAL URBAN": "Hanumakonda",  # renamed in 2021
    "WARANGAL RURAL": "Warangal",
    "WARANGAL": "Warangal",
    "JAYASHANKAR": "Jayashankar Bhupalpally",
    "JAYASHANKAR BHUPALPALLY": "Jayashankar Bhupalpally",
    "BHUPALAPALLI": "Jayashankar Bhupalpally",
    "KOMARAM BHEEM": "Komaram Bheem Asifabad",
    "KOMARAM BHEEM ASIFABAD": "Komaram Bheem Asifabad",
    "ASIFABAD": "Komaram Bheem Asifabad",
    "JOGULAMBA GADWAL": "Jogulamba Gadwal",
    "GADWAL": "Jogulamba Gadwal",
    "BHADRADRI KOTHAGUDEM": "Bhadradri Kothagudem",
    "KOTHAGUDEM": "Bhadradri Kothagudem",
    "MEDCHAL": "Medchal-Malkajgiri",
    "MEDCHAL-MALKAJGIRI": "Medchal-Malkajgiri",
    "MEDCHAL MALKAJGIRI": "Medchal-Malkajgiri",
    "RAJANNA SIRCILLA": "Rajanna Sircilla",
    "SIRCILLA": "Rajanna Sircilla",
    "YADADRI BHUVANAGIRI": "Yadadri Bhuvanagiri",
    "YADADRI": "Yadadri Bhuvanagiri",
    "RANGAREDDY": "Ranga Reddy",
    "RANGA REDDY": "Ranga Reddy",
    "R.R.DIST": "Ranga Reddy",
    # Andhra Pradesh (post-2022 reorganization)
    "YSR": "YSR Kadapa",
    "KADAPA": "YSR Kadapa",
    "YSR KADAPA": "YSR Kadapa",
    "CUDDAPAH": "YSR Kadapa",
    "SPSR NELLORE": "Sri Potti Sriramulu Nellore",
    "NELLORE": "Sri Potti Sriramulu Nellore",
    "SRI POTTI SRIRAMULU NELLORE": "Sri Potti Sriramulu Nellore",
    "SRI SATHYA SAI": "Sri Sathya Sai",
    "SATHYA SAI": "Sri Sathya Sai",
    "ALLURI SITHARAMA RAJU": "Alluri Sitharama Raju",
    "ALLURI SITARAMA RAJU": "Alluri Sitharama Raju",
    "ASR": "Alluri Sitharama Raju",
    "DR. B. R. AMBEDKAR KONASEEMA": "Konaseema",
    "KONASEEMA": "Konaseema",
    "PARVATHIPURAM MANYAM": "Parvathipuram Manyam",
    "NTR": "NTR",
    "N.T.R.": "NTR",
    "N T R": "NTR",
    "VIZIANAGARAM": "Vizianagaram",
    "VISAKHAPATNAM": "Visakhapatnam",
    "EAST GODAVARI": "East Godavari",
    "WEST GODAVARI": "West Godavari",
    "ANANTAPUR": "Anantapur",
    "ANANTHAPUR": "Anantapur",
    "CHITTOOR": "Chittoor",
}


def normalize_key(raw: str) -> str:
    """Strip, collapse internal whitespace (incl. CRLF), uppercase → match key."""
    return re.sub(r"\s+", " ", (raw or "").strip()).upper()


def canonical_state(raw: str) -> str | None:
    """Return canonical state name if `raw` is one of our target states, else None."""
    return TARGET_STATES.get(normalize_key(raw))


def canonical_district(raw: str) -> str:
    """Map a raw DISTRICT string to its canonical name."""
    key = normalize_key(raw)
    if key in DISTRICT_VARIANT_MAP:
        return DISTRICT_VARIANT_MAP[key]
    return key.title()


def clean_taluka(raw: str) -> str:
    """Trim + collapse whitespace, preserve source casing of mandal names."""
    return re.sub(r"\s+", " ", (raw or "").strip())


class Command(BaseCommand):
    help = "Load Telangana + Andhra Pradesh district + mandal boundaries."

    def add_arguments(self, parser):
        parser.add_argument(
            "--source", required=True,
            help="Directory containing states/DISTRICT_BOUNDARY.shp and "
                 "talukas/SUBDISTRICT_BOUNDARY.shp",
        )
        parser.add_argument(
            "--states", default=None,
            help="Comma-separated list of state names to load "
                 "(default: both Telangana and Andhra Pradesh).",
        )
        parser.add_argument(
            "--all", action="store_true", dest="load_all",
            help="Load every district for the target state(s). "
                 "Equivalent to omitting --states.",
        )
        parser.add_argument(
            "--dry-run", action="store_true", dest="dry_run",
            help="Parse, normalize and match but write nothing to the DB.",
        )

    @staticmethod
    def _reproject_to_4326(ogr_geom):
        g = ogr_geom.clone()
        g.coord_dim = 2
        g.transform(4326)
        geos = g.geos
        geos.srid = 4326
        return geos

    @staticmethod
    def _polygons(geos):
        if geos.geom_type == "Polygon":
            yield geos
        elif geos.geom_type == "MultiPolygon":
            yield from list(geos)

    def _to_multipolygon(self, polys):
        return MultiPolygon(list(polys), srid=4326)

    def handle(self, *args, **options):
        try:
            from django.contrib.gis.gdal import DataSource
        except Exception as exc:  # pragma: no cover
            raise CommandError(f"GDAL is required for this command: {exc}") from exc
        from apps.geo.models import District, Taluka

        source = Path(options["source"])
        dry_run = options["dry_run"]

        dist_shp = source / "states" / "DISTRICT_BOUNDARY.shp"
        subd_shp = source / "talukas" / "SUBDISTRICT_BOUNDARY.shp"
        if not dist_shp.exists():
            raise CommandError(f"District shapefile not found: {dist_shp}")
        has_talukas = subd_shp.exists()
        if not has_talukas:
            self.stdout.write(self.style.WARNING(
                f"Sub-district shapefile not found at {subd_shp} — "
                "loading districts only."
            ))

        # Which states to load
        if options["states"]:
            requested = {s.strip() for s in options["states"].split(",") if s.strip()}
            targets = {canon for canon in TARGET_STATES.values() if canon in requested}
            if not targets:
                raise CommandError(
                    f"No valid state in --states={options['states']!r}. "
                    f"Valid: {sorted(set(TARGET_STATES.values()))}"
                )
        else:
            targets = set(TARGET_STATES.values())

        self.stdout.write(f"Source: {source}")
        self.stdout.write(f"Loading states: {sorted(targets)}")
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no database writes."))

        # ── Districts ────────────────────────────────────────────────────────
        # keyed by (state, canonical district name) -> list of polygons
        district_parts: dict[tuple[str, str], list] = {}
        norm_log: set[str] = set()

        ds = DataSource(str(dist_shp))
        for feat in ds[0]:
            state = canonical_state(str(feat.get(STATE_FIELD)))
            if state is None or state not in targets:
                continue
            raw = str(feat.get(DIST_FIELD))
            canon = canonical_district(raw)
            if normalize_key(raw) != canon.upper():
                norm_log.add(f'  {state}: "{raw.strip()}" -> "{canon}"')
            geos = self._reproject_to_4326(feat.geom)
            district_parts.setdefault((state, canon), []).extend(self._polygons(geos))

        if norm_log:
            self.stdout.write("Name-normalization decisions:")
            for line in sorted(norm_log):
                self.stdout.write(line)
                logger.info("normalize %s", line.strip())

        if not district_parts:
            raise CommandError(
                "No matching districts found in shapefile for target states — "
                "check the STATE_UT column values."
            )

        # ── Talukas / mandals ────────────────────────────────────────────────
        taluka_parts: dict[tuple[str, str, str], list] = {}
        if has_talukas:
            ds2 = DataSource(str(subd_shp))
            for feat in ds2[0]:
                state = canonical_state(str(feat.get(STATE_FIELD)))
                if state is None or state not in targets:
                    continue
                canon = canonical_district(str(feat.get(DIST_FIELD)))
                if (state, canon) not in district_parts:
                    continue
                tname = clean_taluka(str(feat.get(SUBDIST_FIELD)))
                geos = self._reproject_to_4326(feat.geom)
                taluka_parts.setdefault((state, canon, tname), []).extend(
                    self._polygons(geos)
                )

        # ── Write ────────────────────────────────────────────────────────────
        d_created = d_updated = t_created = t_updated = 0
        district_objs: dict[tuple[str, str], object] = {}

        if dry_run:
            for (state, canon), parts in sorted(district_parts.items()):
                mpoly = self._to_multipolygon(parts)
                c = mpoly.centroid
                self.stdout.write(
                    f"  [dry] {state:16s} {canon:32s} "
                    f"centroid=({c.y:.4f}N, {c.x:.4f}E) parts={len(parts)}"
                )
            self.stdout.write(self.style.SUCCESS(
                f"DRY RUN OK — {len(district_parts)} districts, "
                f"{len(taluka_parts)} talukas resolved."))
            return

        with transaction.atomic():
            for (state, canon), parts in district_parts.items():
                mpoly = self._to_multipolygon(parts)
                obj, created = District.objects.update_or_create(
                    state=state, name=canon,
                    defaults={"geom": mpoly, "centroid": mpoly.centroid},
                )
                district_objs[(state, canon)] = obj
                d_created += int(created)
                d_updated += int(not created)

            for (state, canon, tname), parts in taluka_parts.items():
                mpoly = self._to_multipolygon(parts)
                _, created = Taluka.objects.update_or_create(
                    district=district_objs[(state, canon)], name=tname,
                    defaults={"geom": mpoly, "centroid": mpoly.centroid},
                )
                t_created += int(created)
                t_updated += int(not created)

        self.stdout.write(self.style.SUCCESS(
            f"Districts: {d_created} created, {d_updated} updated. "
            f"Talukas: {t_created} created, {t_updated} updated."
        ))
