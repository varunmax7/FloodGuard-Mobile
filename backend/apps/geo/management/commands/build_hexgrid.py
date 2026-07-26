"""
build_hexgrid — polyfill an area with H3 hex cells.

Usage:
    manage.py build_hexgrid --from-districts [--res 7]     # polyfill Assam districts
    manage.py build_hexgrid --bbox MIN_LAT MIN_LNG MAX_LAT MAX_LNG [--res 9]
    manage.py build_hexgrid                                # legacy GHMC default

`--from-districts` polyfills the geometric union of every District row in the
DB (loaded by `load_assam_boundaries`), so hexes hug real administrative
borders instead of a rectangular bounding box.
"""
import h3
from django.contrib.gis.db.models import Union
from django.contrib.gis.geos import Point, Polygon
from django.core.management.base import BaseCommand, CommandError

from apps.geo.models import District, HexCell

# GHMC approximate bounding box (lat/lng WGS-84)
GHMC_BBOX = (17.279, 78.218, 17.566, 78.660)  # min_lat, min_lng, max_lat, max_lng


class Command(BaseCommand):
    help = "Polyfill an area with H3 hex cells and upsert HexCell rows."

    def add_arguments(self, parser):
        parser.add_argument(
            "--bbox",
            nargs=4,
            type=float,
            metavar=("MIN_LAT", "MIN_LNG", "MAX_LAT", "MAX_LNG"),
            default=list(GHMC_BBOX),
            help="Bounding box (default: GHMC approximate extent).",
        )
        parser.add_argument(
            "--from-districts", action="store_true", dest="from_districts",
            help="Polyfill the union of all District rows in the DB "
                 "(loaded by load_assam_boundaries). Overrides --bbox.",
        )
        parser.add_argument(
            "--wipe", action="store_true",
            help="Delete every existing HexCell row before rebuilding. Use when "
                 "switching regions (e.g. Hyderabad → Assam) so stale cells "
                 "don't linger in the DB.",
        )
        parser.add_argument(
            "--res",
            type=int,
            default=9,
            help="H3 resolution (default 9, edge ~174 m; use 7 for state-scale).",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=500,
            dest="batch_size",
        )

    def handle(self, *args, **options):
        res = options["res"]
        batch_size = options["batch_size"]

        if options["wipe"]:
            n = HexCell.objects.count()
            HexCell.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"Wiped {n} existing HexCell rows."))

        if options["from_districts"]:
            if not District.objects.exists():
                raise CommandError(
                    "No District rows found. Run `load_assam_boundaries` first."
                )
            self.stdout.write(
                f"Polyfilling union of {District.objects.count()} districts "
                f"at H3 res {res} ..."
            )
            merged = District.objects.aggregate(g=Union("geom"))["g"]
            geo = self._geos_to_geojson(merged)
        else:
            min_lat, min_lng, max_lat, max_lng = options["bbox"]
            # GeoJSON polygon — GeoJSON uses (lng, lat) ordering
            geo = {
                "type": "Polygon",
                "coordinates": [[
                    [min_lng, min_lat],
                    [max_lng, min_lat],
                    [max_lng, max_lat],
                    [min_lng, max_lat],
                    [min_lng, min_lat],
                ]],
            }
            self.stdout.write(
                f"Polyfilling bbox ({min_lat},{min_lng}) → ({max_lat},{max_lng}) "
                f"at H3 res {res} ..."
            )

        cells = list(h3.geo_to_cells(geo, res))
        self.stdout.write(f"  {len(cells)} cells to process.")

        total_created = total_updated = 0
        for i in range(0, len(cells), batch_size):
            batch_cells = cells[i : i + batch_size]
            created, updated = self._upsert_batch(batch_cells)
            total_created += created
            total_updated += updated
            self.stdout.write(
                f"  [{i + len(batch_cells)}/{len(cells)}] "
                f"created={total_created} updated={total_updated}"
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Done — {total_created} created, {total_updated} updated, "
                f"{total_created + total_updated} total HexCell rows."
            )
        )

    @staticmethod
    def _geos_to_geojson(geom) -> dict:
        """Convert a GEOS Polygon/MultiPolygon to a GeoJSON geometry dict.

        h3.geo_to_cells accepts both Polygon and MultiPolygon GeoJSON.
        """
        gt = geom.geom_type
        if gt == "Polygon":
            return {
                "type": "Polygon",
                "coordinates": [
                    [list(pt) for pt in ring.coords]
                    for ring in geom
                ],
            }
        if gt == "MultiPolygon":
            return {
                "type": "MultiPolygon",
                "coordinates": [
                    [[list(pt) for pt in ring.coords] for ring in poly]
                    for poly in geom
                ],
            }
        raise ValueError(f"Unsupported geometry type for polyfill: {gt}")

    def _upsert_batch(self, cell_ids: list[str]) -> tuple[int, int]:
        existing_map = {
            hc.h3_index: hc
            for hc in HexCell.objects.filter(h3_index__in=cell_ids)
        }

        to_create = []
        to_update = []
        for cell in cell_ids:
            boundary = h3.cell_to_boundary(cell)  # list of (lat, lng) tuples
            # PostGIS / Django GIS expects (lng, lat) ordering
            ring = [(lng, lat) for lat, lng in boundary]
            ring.append(ring[0])  # close the ring
            geom = Polygon(ring, srid=4326)

            lat, lng = h3.cell_to_latlng(cell)
            centroid = Point(lng, lat, srid=4326)

            if cell in existing_map:
                obj = existing_map[cell]
                obj.geom = geom
                obj.centroid = centroid
                to_update.append(obj)
            else:
                to_create.append(
                    HexCell(h3_index=cell, geom=geom, centroid=centroid)
                )

        if to_create:
            HexCell.objects.bulk_create(to_create, ignore_conflicts=True)
        if to_update:
            HexCell.objects.bulk_update(to_update, ["geom", "centroid"])

        return len(to_create), len(to_update)
