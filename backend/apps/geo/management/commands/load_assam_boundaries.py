"""
load_assam_boundaries — ingest Assam district + sub-district (taluka) boundaries
into the District / Taluka tables (pA0, emergency Assam flood scope).

Source data
-----------
Survey of India / data.gov.in administrative boundary shapefiles:
    <source>/states/DISTRICT_BOUNDARY.shp        (all-India districts)
    <source>/talukas/SUBDISTRICT_BOUNDARY.shp    (all-India sub-districts)

These carry official STATE_LGD / DIST_LGD codes and are in a projected CRS
(Lambert Conformal Conic, metres) — geometries are reprojected to EPSG:4326
using each layer's own .prj via GDAL before storage.

Why a normalization map (and not exact string matching)
-------------------------------------------------------
Assam district name strings in these datasets are inconsistent:
  * trailing CRLF whitespace  ("BAKSA\\r\\n")
  * all-caps                  ("SIVASAGAR")
  * spelling variants         (SIBSAGAR->Sivasagar, MARIGAON->Morigaon,
                               DARANG->Darrang)
  * cross-file typos          (district file "KARBI ANGLONG" vs sub-district
                               file "KARBI ANAGLONG")
  * renamed districts         (KARIMGANJ -> Sribhumi)
Every feature's DISTRICT string is therefore normalized (strip + collapse
whitespace + explicit variant map, with a Title-case fallback) to a canonical
name.  Every non-trivial decision is logged so the mapping is auditable.

Idempotent: upserts by canonical District.name and by (district, Taluka.name),
safe to re-run.  Fails loudly (CommandError) if any confirmed district has no
match in the source data after normalization — it never silently drops one.

Usage
-----
    manage.py load_assam_boundaries --source /path/to/fg_app/boundaries
    manage.py load_assam_boundaries --source ... --districts "Golaghat,Jorhat,..."
    manage.py load_assam_boundaries --source ... --dry-run
"""
import logging
import re
from pathlib import Path

from django.contrib.gis.geos import MultiPolygon
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

logger = logging.getLogger("floodguard.geo")

# ── Canonical name resolution ────────────────────────────────────────────────
# normalized-uppercase key  ->  canonical district name.
# Covers every Assam district we know a variant for (not only the confirmed
# scope) so the mapping stays valid if the scope is widened later.
DISTRICT_VARIANT_MAP = {
    "KAMRUP RURAL": "Kamrup", "KAMRUP": "Kamrup",
    "KAMRUP METRO": "Kamrup Metropolitan", "KAMRUP METROPOLITAN": "Kamrup Metropolitan",
    "SIBSAGAR": "Sivasagar", "SIVASAGAR": "Sivasagar", "SHIVSAGAR": "Sivasagar",
    "NAGAON": "Nagaon", "NOWGONG": "Nagaon",
    "KARBI ANGLONG": "Karbi Anglong", "KARBI-ANGLONG": "Karbi Anglong",
    "KARBI ANAGLONG": "Karbi Anglong",  # sub-district-file typo
    "WEST KARBI ANGLONG": "West Karbi Anglong",
    "WEST KARBI ANAGLONG": "West Karbi Anglong",
    "DIMA HASAO": "Dima Hasao", "DIMA HASAO (N.C. HILLS)": "Dima Hasao",
    "NORTH CACHAR HILLS": "Dima Hasao",
    "MARIGAON": "Morigaon", "MORIGAON": "Morigaon",
    "DARANG": "Darrang", "DARRANG": "Darrang",
    "SRIBHUMI": "Sribhumi", "KARIMGANJ": "Sribhumi",
    "SOUTH SALMARA": "South Salmara-Mankachar",
    "SOUTH SALMARA MANKACHAR": "South Salmara-Mankachar",
    "SOUTH SALMARA-MANKACHAR": "South Salmara-Mankachar",
}

# Confirmed flood-affected districts (ASDMA bulletin). Kamrup (rural) and Kamrup
# Metropolitan are deliberately two distinct entries.
DEFAULT_CONFIRMED = [
    "Golaghat", "Hojai", "Kamrup", "Charaideo", "Jorhat", "Dibrugarh",
    "Sivasagar", "Nagaon", "Kamrup Metropolitan", "Karbi Anglong", "Tinsukia",
]

STATE_FIELD = "STATE_UT"
DIST_FIELD = "DISTRICT"
SUBDIST_FIELD = "SUB_DIST"
TARGET_STATE = "ASSAM"


def normalize_key(raw: str) -> str:
    """Strip, collapse internal whitespace (incl. CRLF), uppercase → match key."""
    return re.sub(r"\s+", " ", (raw or "").strip()).upper()


def canonical_district(raw: str) -> str:
    """Map a raw DISTRICT string to its canonical name."""
    key = normalize_key(raw)
    if key in DISTRICT_VARIANT_MAP:
        return DISTRICT_VARIANT_MAP[key]
    return key.title()  # fallback: e.g. "GOLAGHAT" -> "Golaghat"


def clean_taluka(raw: str) -> str:
    """Trim + collapse whitespace, preserve the source casing of circle names."""
    return re.sub(r"\s+", " ", (raw or "").strip())


class Command(BaseCommand):
    help = "Load Assam district + taluka boundaries into District/Taluka (pA0)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--source", required=True,
            help="Directory containing states/DISTRICT_BOUNDARY.shp and "
                 "talukas/SUBDISTRICT_BOUNDARY.shp",
        )
        parser.add_argument(
            "--districts", default=None,
            help="Comma-separated canonical district names to scope to. "
                 "Defaults to the 11 confirmed flood-affected districts.",
        )
        parser.add_argument(
            "--all", action="store_true", dest="load_all",
            help="Load every Assam district present in the shapefile "
                 "(overrides --districts and the default 11-district scope).",
        )
        parser.add_argument(
            "--dry-run", action="store_true", dest="dry_run",
            help="Parse, normalize and match but write nothing to the DB.",
        )

    # ── geometry helpers ─────────────────────────────────────────────────────
    @staticmethod
    def _reproject_to_4326(ogr_geom):
        """Flatten Z and reproject an OGR geometry to EPSG:4326 → GEOS geometry."""
        g = ogr_geom.clone()
        g.coord_dim = 2                      # drop Z (source is POLYGON Z)
        g.transform(4326)                    # uses the layer .prj as source CRS
        geos = g.geos
        geos.srid = 4326
        return geos

    @staticmethod
    def _polygons(geos):
        """Yield constituent Polygon(s) from a Polygon or MultiPolygon."""
        if geos.geom_type == "Polygon":
            yield geos
        elif geos.geom_type == "MultiPolygon":
            yield from list(geos)

    def _to_multipolygon(self, polys):
        """Combine constituent Polygon(s) into a single 4326 MultiPolygon."""
        return MultiPolygon(list(polys), srid=4326)

    # ── main ─────────────────────────────────────────────────────────────────
    def handle(self, *args, **options):
        try:
            from django.contrib.gis.gdal import DataSource
        except Exception as exc:  # pragma: no cover
            raise CommandError(f"GDAL is required for this command: {exc}") from exc
        from apps.geo.models import District, Taluka

        source = Path(options["source"])
        dry_run = options["dry_run"]
        load_all = options["load_all"]

        dist_shp = source / "states" / "DISTRICT_BOUNDARY.shp"
        subd_shp = source / "talukas" / "SUBDISTRICT_BOUNDARY.shp"
        for p in (dist_shp, subd_shp):
            if not p.exists():
                raise CommandError(f"Boundary shapefile not found: {p}")

        # In --all mode, discover every Assam district present in the shapefile
        # up front so the rest of the pipeline (which still gates on
        # confirmed_set for auditability) accepts them all.
        if load_all:
            discovered: set[str] = set()
            _ds = DataSource(str(dist_shp))
            for feat in _ds[0]:
                if normalize_key(str(feat.get(STATE_FIELD))) != TARGET_STATE:
                    continue
                discovered.add(canonical_district(str(feat.get(DIST_FIELD))))
            confirmed = sorted(discovered)
        else:
            confirmed = (
                [c.strip() for c in options["districts"].split(",") if c.strip()]
                if options["districts"] else list(DEFAULT_CONFIRMED)
            )
        confirmed_set = set(confirmed)

        self.stdout.write(f"Source: {source}")
        self.stdout.write(f"Confirmed districts ({len(confirmed)}): {', '.join(confirmed)}")
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no database writes."))

        # ── Districts: collect polygon parts per canonical name ──────────────
        district_parts: dict[str, list] = {}
        norm_log: set[str] = set()

        ds = DataSource(str(dist_shp))
        layer = ds[0]
        for feat in layer:
            if normalize_key(str(feat.get(STATE_FIELD))) != TARGET_STATE:
                continue
            raw = str(feat.get(DIST_FIELD))
            canon = canonical_district(raw)
            if canon not in confirmed_set:
                continue
            if normalize_key(raw) != canon.upper():
                norm_log.add(f'  district: "{raw.strip()}" -> "{canon}"')
            geos = self._reproject_to_4326(feat.geom)
            district_parts.setdefault(canon, []).extend(self._polygons(geos))

        # Log every non-trivial normalization decision (auditable mapping).
        if norm_log:
            self.stdout.write("Name-normalization decisions:")
            for line in sorted(norm_log):
                self.stdout.write(line)
                logger.info("normalize %s", line.strip())

        # ── Fail loudly on any unmatched confirmed district ──────────────────
        missing = [d for d in confirmed if d not in district_parts]
        if missing:
            raise CommandError(
                "No boundary match for confirmed district(s) after "
                f"normalization: {missing}. Aborting — refusing to silently "
                "drop a flood-affected district."
            )

        # ── Talukas: collect polygon parts per (district, taluka) ────────────
        taluka_parts: dict[tuple[str, str], list] = {}
        ds2 = DataSource(str(subd_shp))
        layer2 = ds2[0]
        for feat in layer2:
            if normalize_key(str(feat.get(STATE_FIELD))) != TARGET_STATE:
                continue
            canon = canonical_district(str(feat.get(DIST_FIELD)))
            if canon not in confirmed_set:
                continue
            tname = clean_taluka(str(feat.get(SUBDIST_FIELD)))
            geos = self._reproject_to_4326(feat.geom)
            taluka_parts.setdefault((canon, tname), []).extend(self._polygons(geos))

        # ── Write (idempotent upsert) ────────────────────────────────────────
        d_created = d_updated = t_created = t_updated = 0
        district_objs: dict[str, object] = {}

        if dry_run:
            for canon in confirmed:
                mpoly = self._to_multipolygon(district_parts[canon])
                c = mpoly.centroid
                self.stdout.write(
                    f"  [dry] District {canon:22s} "
                    f"centroid=({c.y:.4f}N, {c.x:.4f}E) parts={len(district_parts[canon])}"
                )
            t_by_d: dict[str, int] = {}
            for (canon, _t) in taluka_parts:
                t_by_d[canon] = t_by_d.get(canon, 0) + 1
            for canon in confirmed:
                self.stdout.write(f"  [dry] {canon:22s} talukas={t_by_d.get(canon, 0)}")
            self.stdout.write(self.style.SUCCESS(
                f"DRY RUN OK — {len(confirmed)} districts, "
                f"{len(taluka_parts)} talukas resolved."))
            return

        with transaction.atomic():
            for canon in confirmed:
                mpoly = self._to_multipolygon(district_parts[canon])
                obj, created = District.objects.update_or_create(
                    name=canon,
                    defaults={"state": "Assam", "geom": mpoly, "centroid": mpoly.centroid},
                )
                district_objs[canon] = obj
                d_created += int(created)
                d_updated += int(not created)

            for (canon, tname), parts in taluka_parts.items():
                mpoly = self._to_multipolygon(parts)
                _, created = Taluka.objects.update_or_create(
                    district=district_objs[canon], name=tname,
                    defaults={"geom": mpoly, "centroid": mpoly.centroid},
                )
                t_created += int(created)
                t_updated += int(not created)

        self.stdout.write(self.style.SUCCESS(
            f"Districts: {d_created} created, {d_updated} updated. "
            f"Talukas: {t_created} created, {t_updated} updated."
        ))
