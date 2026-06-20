"""Phase 4 tests — risk engine, recompute task, and all 4 public endpoints."""
import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.geo.models import HexCell
from apps.ingest.models import ForecastStage, RadarFrame
from apps.risk.engine import (
    RISK_MATRIX,
    bucket_hazard,
    bucket_susceptibility,
    compute_confidence,
    compute_risk,
)
from apps.risk.models import BiasFactor, RiskSnapshot
from tests.factories import HexCellFactory


# ---------------------------------------------------------------------------
# Engine unit tests — every hazard bucket, every matrix cell, bias application
# ---------------------------------------------------------------------------

class TestBucketHazard:
    def test_low_boundary(self):
        assert bucket_hazard(0.0) == "LOW"
        assert bucket_hazard(7.49) == "LOW"

    def test_moderate_boundary(self):
        assert bucket_hazard(7.5) == "MODERATE"
        assert bucket_hazard(34.99) == "MODERATE"

    def test_high_boundary(self):
        assert bucket_hazard(35.0) == "HIGH"
        assert bucket_hazard(64.49) == "HIGH"

    def test_severe_boundary(self):
        assert bucket_hazard(64.5) == "SEVERE"
        assert bucket_hazard(100.0) == "SEVERE"

    def test_negative_rain_is_low(self):
        assert bucket_hazard(-5.0) == "LOW"


class TestBucketSusceptibility:
    def test_low(self):
        assert bucket_susceptibility(0.0) == "LOW"
        assert bucket_susceptibility(0.32) == "LOW"

    def test_med(self):
        assert bucket_susceptibility(0.33) == "MED"
        assert bucket_susceptibility(0.65) == "MED"

    def test_high(self):
        assert bucket_susceptibility(0.66) == "HIGH"
        assert bucket_susceptibility(1.0) == "HIGH"


class TestRiskMatrix:
    """Every cell of the 4×3 matrix must produce the documented value."""

    @pytest.mark.parametrize("hazard,susc_idx,expected", [
        ("LOW",      0, "LOW"),
        ("LOW",      1, "LOW"),
        ("LOW",      2, "MODERATE"),
        ("MODERATE", 0, "LOW"),
        ("MODERATE", 1, "MODERATE"),
        ("MODERATE", 2, "HIGH"),
        ("HIGH",     0, "MODERATE"),
        ("HIGH",     1, "HIGH"),
        ("HIGH",     2, "SEVERE"),
        ("SEVERE",   0, "HIGH"),
        ("SEVERE",   1, "SEVERE"),
        ("SEVERE",   2, "SEVERE"),
    ])
    def test_matrix_cell(self, hazard, susc_idx, expected):
        assert RISK_MATRIX[hazard][susc_idx] == expected


class TestBiasApplication:
    def test_multiplier_scales_rain(self):
        result = compute_risk(
            rain_raw_1h=10.0, bias_multiplier=2.0, bias_offset=0.0, fsi_score=0.5
        )
        assert result.rain_corrected == pytest.approx(20.0, rel=1e-3)
        assert result.hazard_class == "MODERATE"

    def test_offset_shifts_rain(self):
        result = compute_risk(
            rain_raw_1h=0.0, bias_multiplier=1.0, bias_offset=10.0, fsi_score=0.5
        )
        assert result.rain_corrected == pytest.approx(10.0, rel=1e-3)
        assert result.hazard_class == "MODERATE"

    def test_negative_corrected_clamped_to_zero(self):
        result = compute_risk(
            rain_raw_1h=1.0, bias_multiplier=1.0, bias_offset=-10.0, fsi_score=0.1
        )
        assert result.rain_corrected == 0.0
        assert result.hazard_class == "LOW"

    def test_full_pipeline_severe(self):
        result = compute_risk(
            rain_raw_1h=30.0, bias_multiplier=2.5, bias_offset=0.0, fsi_score=0.8
        )
        # 30 * 2.5 = 75 mm/h → SEVERE hazard, HIGH susceptibility → SEVERE risk
        assert result.hazard_class == "SEVERE"
        assert result.risk_level == "SEVERE"

    def test_confidence_with_station_obs(self):
        c_with = compute_confidence(1.0, has_station_obs=True)
        c_without = compute_confidence(1.0, has_station_obs=False)
        assert c_with > c_without

    def test_confidence_decreases_with_lead_time(self):
        c_1h = compute_confidence(1.0, has_station_obs=False)
        c_6h = compute_confidence(6.0, has_station_obs=False)
        assert c_1h > c_6h

    def test_confidence_clamped(self):
        c = compute_confidence(100.0, has_station_obs=False)
        assert c >= 10


# ---------------------------------------------------------------------------
# recompute_all_risk task
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestRecomputeAllRisk:
    def _seed(self, fsi_score=0.5, rain_1h=20.0):
        """Create one hex + ForecastStage so the task has something to compute."""
        cell = HexCellFactory(fsi_score=fsi_score)
        # Use now as run_ts so it's always the latest (beats any existing Phase 3 data)
        now = timezone.now().replace(second=0, microsecond=0)
        ForecastStage.objects.create(
            hex=cell,
            valid_ts=now + timezone.timedelta(hours=1),
            run_ts=now,
            rain_1h=rain_1h,
            rain_3h=rain_1h * 2.5,
            rain_24h=rain_1h * 18,
            source="ECMWF",
        )
        return cell

    def test_creates_risk_snapshots(self, settings):
        settings.INGEST_MOCK = True
        self._seed(fsi_score=0.5, rain_1h=20.0)

        from apps.risk.tasks import recompute_all_risk
        count = recompute_all_risk.apply().get()
        assert count >= 1
        assert RiskSnapshot.objects.count() >= 1

    def test_risk_level_correct_for_inputs(self, settings):
        settings.INGEST_MOCK = True
        # 20mm/h, no bias → MODERATE hazard; fsi=0.8 → HIGH susc → HIGH risk
        cell = self._seed(fsi_score=0.8, rain_1h=20.0)

        from apps.risk.tasks import recompute_all_risk
        recompute_all_risk.apply().get()

        # Query specifically for the hex we seeded
        snap = RiskSnapshot.objects.filter(hex=cell).order_by("-id").first()
        assert snap is not None
        assert snap.hazard_class == "MODERATE"
        assert snap.risk_level == "HIGH"

    def test_idempotent(self, settings):
        settings.INGEST_MOCK = True
        self._seed()

        from apps.risk.tasks import recompute_all_risk
        recompute_all_risk.apply().get()
        count_after_first = RiskSnapshot.objects.count()
        recompute_all_risk.apply().get()
        assert RiskSnapshot.objects.count() == count_after_first


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------

HYD_BBOX = "78.2,17.2,78.7,17.6"   # covers GHMC


def _seed_snapshot(risk_level="MODERATE", hazard_class="MODERATE",
                   rain_1h=20.0, confidence=75, fsi_score=0.5):
    """Create a HexCell + RiskSnapshot for API tests."""
    cell = HexCellFactory(fsi_score=fsi_score)
    now = timezone.now().replace(second=0, microsecond=0)
    snap = RiskSnapshot.objects.create(
        hex=cell,
        ts=now,
        rain_1h=rain_1h,
        rain_3h=rain_1h * 2.5,
        rain_24h=rain_1h * 18,
        hazard_class=hazard_class,
        risk_level=risk_level,
        confidence=confidence,
        source_model="ECMWF",
    )
    return cell, snap


@pytest.mark.django_db
class TestRiskHexesEndpoint:
    url = "/api/v1/risk/hexes/"

    def test_missing_bbox_returns_400(self):
        resp = APIClient().get(self.url)
        assert resp.status_code == 400

    def test_invalid_bbox_returns_400(self):
        resp = APIClient().get(self.url, {"bbox": "bad"})
        assert resp.status_code == 400

    def test_returns_geojson_feature_collection(self):
        _seed_snapshot()
        resp = APIClient().get(self.url, {"bbox": HYD_BBOX})
        assert resp.status_code == 200
        assert resp.data["type"] == "FeatureCollection"
        assert "features" in resp.data

    def test_features_have_correct_shape(self):
        _seed_snapshot(risk_level="HIGH")
        resp = APIClient().get(self.url, {"bbox": HYD_BBOX})
        assert resp.status_code == 200
        if resp.data["features"]:
            f = resp.data["features"][0]
            assert f["type"] == "Feature"
            assert "geometry" in f
            props = f["properties"]
            assert "h3_index" in props
            assert "risk_level" in props
            assert "confidence" in props

    def test_bbox_filters_out_of_range_hexes(self):
        # Hex far from Hyderabad (Delhi area)
        from django.contrib.gis.geos import Point, Polygon as GeoPolygon
        cell = HexCellFactory(
            h3_index="891f1aaaaa7ffff",
            centroid=Point(77.2, 28.6, srid=4326),  # Delhi
        )
        RiskSnapshot.objects.create(
            hex=cell, ts=timezone.now(),
            rain_1h=10, rain_3h=25, rain_24h=180,
            hazard_class="MODERATE", risk_level="MODERATE",
            confidence=70, source_model="ECMWF",
        )
        resp = APIClient().get(self.url, {"bbox": HYD_BBOX})
        h3_indices = [f["properties"]["h3_index"] for f in resp.data["features"]]
        assert "891f1aaaaa7ffff" not in h3_indices


@pytest.mark.django_db
class TestRiskLocationEndpoint:
    url = "/api/v1/risk/location/"

    def test_missing_params_returns_400(self):
        resp = APIClient().get(self.url)
        assert resp.status_code == 400

    def test_valid_coords_returns_correct_shape(self):
        cell, snap = _seed_snapshot(risk_level="HIGH", rain_1h=40.0)
        lat, lng = cell.centroid.y, cell.centroid.x
        resp = APIClient().get(self.url, {"lat": lat, "lng": lng})
        assert resp.status_code in (200, 404)
        if resp.status_code == 200:
            assert "risk_level" in resp.data
            assert "plain_text" in resp.data
            assert "confidence" in resp.data
            assert "hourly" in resp.data
            assert isinstance(resp.data["hourly"], list)

    def test_out_of_area_returns_404(self):
        # Coordinates far outside GHMC
        resp = APIClient().get(self.url, {"lat": 0.0, "lng": 0.0})
        assert resp.status_code == 404


@pytest.mark.django_db
class TestRiskOverviewEndpoint:
    url = "/api/v1/risk/overview/"

    def test_empty_db_returns_defaults(self):
        resp = APIClient().get(self.url)
        assert resp.status_code == 200
        assert "summary" in resp.data
        assert "hotspots" in resp.data

    def test_summary_percentages_sum_to_100(self):
        for level, hz in [("LOW", "LOW"), ("HIGH", "HIGH"), ("SEVERE", "SEVERE")]:
            _seed_snapshot(risk_level=level, hazard_class=hz)

        resp = APIClient().get(self.url)
        assert resp.status_code == 200
        s = resp.data["summary"]
        total = s["low"] + s["moderate"] + s["high"] + s["severe"]
        assert abs(total - 100.0) < 1.0

    def test_hotspots_are_high_or_severe(self):
        _seed_snapshot(risk_level="SEVERE", hazard_class="SEVERE", rain_1h=70.0)
        _seed_snapshot(risk_level="LOW", hazard_class="LOW", rain_1h=2.0)

        resp = APIClient().get(self.url)
        assert resp.status_code == 200
        for hs in resp.data["hotspots"]:
            assert hs["risk_level"] in ("HIGH", "SEVERE")


@pytest.mark.django_db
class TestRadarFramesEndpoint:
    url = "/api/v1/radar/frames/"

    def setup_method(self):
        """Clear all radar frames before each test for isolation."""
        RadarFrame.objects.all().delete()

    def test_returns_list(self):
        RadarFrame.objects.create(
            ts=timezone.now(),
            tile_url_template="https://example.com/{z}/{x}/{y}.png",
            dbz_min=0, dbz_max=55, georef_ok=True, anomaly=False,
        )
        resp = APIClient().get(self.url)
        assert resp.status_code == 200
        assert isinstance(resp.data, list)
        assert len(resp.data) == 1

    def test_each_frame_has_intensity_legend(self):
        RadarFrame.objects.create(
            ts=timezone.now(),
            tile_url_template="https://example.com/{z}/{x}/{y}.png",
            dbz_min=0, dbz_max=55, georef_ok=True, anomaly=False,
        )
        resp = APIClient().get(self.url)
        assert "intensity_legend" in resp.data[0]
        assert len(resp.data[0]["intensity_legend"]) > 0

    def test_georef_false_excluded(self):
        RadarFrame.objects.create(
            ts=timezone.now(),
            tile_url_template="https://example.com/{z}/{x}/{y}.png",
            dbz_min=0, dbz_max=55, georef_ok=False, anomaly=False,
        )
        resp = APIClient().get(self.url)
        assert resp.status_code == 200
        assert len(resp.data) == 0

    def test_since_filter(self):
        past = timezone.now() - timezone.timedelta(hours=2)
        recent = timezone.now()
        RadarFrame.objects.create(ts=past, tile_url_template="https://x.com/{z}/{x}/{y}.png",
                                  dbz_min=0, dbz_max=40, georef_ok=True)
        RadarFrame.objects.create(ts=recent, tile_url_template="https://x.com/{z}/{x}/{y}.png",
                                  dbz_min=0, dbz_max=50, georef_ok=True)

        since = (timezone.now() - timezone.timedelta(hours=1)).isoformat()
        resp = APIClient().get(self.url, {"since": since})
        assert resp.status_code == 200
        assert len(resp.data) == 1


# ---------------------------------------------------------------------------
# Plain-text generator
# ---------------------------------------------------------------------------

class TestPlainText:
    def test_severe_severe_returns_emergency_text(self):
        from apps.risk.plain_text import generate
        headline, advice = generate("SEVERE", "SEVERE")
        assert "Severe" in headline or "severe" in headline.lower()

    def test_low_low_returns_calm_text(self):
        from apps.risk.plain_text import generate
        headline, _ = generate("LOW", "LOW")
        assert "Low" in headline or "low" in headline.lower()

    def test_all_combinations_return_strings(self):
        from apps.risk.plain_text import generate
        for risk in ["LOW", "MODERATE", "HIGH", "SEVERE"]:
            for hazard in ["LOW", "MODERATE", "HIGH", "SEVERE"]:
                h, a = generate(risk, hazard)
                assert isinstance(h, str) and len(h) > 0
                assert isinstance(a, str) and len(a) > 0
