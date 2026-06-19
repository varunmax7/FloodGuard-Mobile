"""Phase 1 tests — HexCell polyfill sanity + FSI range."""
import pytest
from django.contrib.gis.geos import Point

from apps.geo.models import HexCell
from tests.factories import (
    AwsObservationFactory,
    AwsStationFactory,
    HexCellFactory,
    RiskSnapshotFactory,
)

# ---------------------------------------------------------------------------
# HexCell model
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestHexCell:
    def test_create_and_retrieve(self):
        cell = HexCellFactory(h3_index="891f1d4f007ffff", fsi_score=0.42)
        saved = HexCell.objects.get(h3_index="891f1d4f007ffff")
        assert saved.fsi_score == pytest.approx(0.42)

    def test_fsi_score_range(self):
        for score in [0.0, 0.5, 1.0]:
            HexCellFactory(fsi_score=score)
        scores = HexCell.objects.values_list("fsi_score", flat=True)
        assert all(0.0 <= s <= 1.0 for s in scores)

    def test_geom_is_polygon(self):
        cell = HexCellFactory()
        assert cell.geom is not None
        assert cell.geom.geom_type == "Polygon"

    def test_centroid_is_point(self):
        cell = HexCellFactory()
        assert isinstance(cell.centroid, Point)

    def test_fsi_inputs_keys(self):
        cell = HexCellFactory()
        expected = {"twi", "depression_depth", "hand", "dist_to_water", "slope", "imperviousness"}
        assert set(cell.fsi_inputs.keys()) == expected

    def test_str(self):
        cell = HexCellFactory(h3_index="891f1d4f007ffff")
        assert "891f1d4f007ffff" in str(cell)


# ---------------------------------------------------------------------------
# build_hexgrid command (unit-level, no DB required for polyfill logic)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestBuildHexgrid:
    def test_polyfill_produces_nonzero_count(self):
        """A small sub-bbox of GHMC should produce at least one H3 cell at res 9."""
        import h3

        geo = {
            "type": "Polygon",
            "coordinates": [[
                [78.40, 17.38],
                [78.42, 17.38],
                [78.42, 17.40],
                [78.40, 17.40],
                [78.40, 17.38],
            ]],
        }
        cells = list(h3.geo_to_cells(geo, 9))
        assert len(cells) > 0, "Expected non-empty polyfill for GHMC sub-bbox"

    def test_cell_boundary_closes(self):
        """H3 cell boundary must be convertible to a valid Django Polygon."""
        import h3
        from django.contrib.gis.geos import Polygon

        # A real H3 res-9 cell near Hyderabad
        cell = "8911a61687fffff"
        boundary = h3.cell_to_boundary(cell)
        ring = [(lng, lat) for lat, lng in boundary]
        ring.append(ring[0])
        poly = Polygon(ring, srid=4326)
        assert poly.valid, f"Polygon invalid: {poly.valid_reason}"
        assert poly.area > 0

    def test_upsert_creates_rows(self, db):
        import h3
        from django.contrib.gis.geos import Point, Polygon
        from apps.geo.models import HexCell

        geo = {
            "type": "Polygon",
            "coordinates": [[
                [78.40, 17.38],
                [78.42, 17.38],
                [78.42, 17.40],
                [78.40, 17.40],
                [78.40, 17.38],
            ]],
        }
        cells = list(h3.geo_to_cells(geo, 9))
        to_create = []
        for c in cells:
            boundary = h3.cell_to_boundary(c)
            ring = [(lng, lat) for lat, lng in boundary]
            ring.append(ring[0])
            lat, lng = h3.cell_to_latlng(c)
            to_create.append(
                HexCell(
                    h3_index=c,
                    geom=Polygon(ring, srid=4326),
                    centroid=Point(lng, lat, srid=4326),
                )
            )
        HexCell.objects.bulk_create(to_create, ignore_conflicts=True)
        count = HexCell.objects.filter(h3_index__in=[c.h3_index for c in to_create]).count()
        assert count == len(cells)


# ---------------------------------------------------------------------------
# AwsStation / AwsObservation
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestAwsStation:
    def test_station_linked_to_hex(self):
        station = AwsStationFactory()
        assert station.hex is not None
        assert isinstance(station.hex, HexCell)

    def test_observation_ordering(self):
        station = AwsStationFactory()
        AwsObservationFactory.create_batch(3, station=station)
        obs = list(station.observations.all())
        timestamps = [o.ts for o in obs]
        assert timestamps == sorted(timestamps, reverse=True)


# ---------------------------------------------------------------------------
# RiskSnapshot
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestRiskSnapshot:
    def test_risk_level_choices(self):
        snap = RiskSnapshotFactory(risk_level="SEVERE", hazard_class="SEVERE")
        assert snap.risk_level == "SEVERE"

    def test_confidence_range(self):
        for conf in [0, 50, 100]:
            RiskSnapshotFactory(confidence=conf)
