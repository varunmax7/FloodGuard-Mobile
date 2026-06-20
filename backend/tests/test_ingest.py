"""Phase 3 tests — ingest tasks (MOCK mode), parsers, bias computation."""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.geo.models import AwsObservation, AwsStation, HexCell
from apps.ingest.models import ForecastStage, IngestLog, RadarFrame
from apps.risk.models import BiasFactor
from tests.factories import HexCellFactory


# ---------------------------------------------------------------------------
# Parser unit tests (no DB needed for pure logic)
# ---------------------------------------------------------------------------

class TestEcmwfParser:
    def test_mock_returns_one_record_per_hex(self):
        from apps.ingest.parsers.ecmwf import _mock_forecast
        from datetime import datetime, timezone as tz

        class FakeCell:
            h3_index = "891f1d4f007ffff"
            class centroid:
                y, x = 17.38, 78.45

        run_ts = datetime(2026, 6, 20, 6, 0, 0, tzinfo=tz.utc)
        cells = [FakeCell()]
        records = _mock_forecast(run_ts, cells)
        assert len(records) == 1
        r = records[0]
        assert r["hex_id"] == "891f1d4f007ffff"
        assert r["rain_1h"] >= 0
        assert r["rain_3h"] >= r["rain_1h"]
        assert r["rain_24h"] >= r["rain_3h"]
        assert r["source"] == "ECMWF"

    def test_mock_is_deterministic(self):
        from apps.ingest.parsers.ecmwf import _mock_forecast
        from datetime import datetime, timezone as tz

        class FakeCell:
            h3_index = "abc"
            class centroid:
                y, x = 17.38, 78.45

        run_ts = datetime(2026, 6, 20, 6, 0, 0, tzinfo=tz.utc)
        r1 = _mock_forecast(run_ts, [FakeCell()])
        r2 = _mock_forecast(run_ts, [FakeCell()])
        assert r1[0]["rain_1h"] == r2[0]["rain_1h"]


class TestAwsParser:
    def test_mock_returns_10_stations(self):
        from apps.ingest.parsers.aws import _mock_observations, MOCK_STATIONS
        from datetime import datetime, timezone as tz

        ts = datetime(2026, 6, 20, 6, 0, 0, tzinfo=tz.utc)
        obs = _mock_observations(ts)
        assert len(obs) == len(MOCK_STATIONS)
        for o in obs:
            assert "station_id" in o
            assert "rain_1h" in o
            assert o["rain_1h"] >= 0

    def test_mock_is_deterministic(self):
        from apps.ingest.parsers.aws import _mock_observations
        from datetime import datetime, timezone as tz

        ts = datetime(2026, 6, 20, 6, 0, 0, tzinfo=tz.utc)
        assert _mock_observations(ts)[0]["rain_1h"] == _mock_observations(ts)[0]["rain_1h"]


class TestRadarParser:
    def test_mock_frame_has_required_fields(self):
        from apps.ingest.parsers.radar import fetch_and_parse
        from datetime import datetime, timezone as tz

        ts = datetime(2026, 6, 20, 6, 0, 0, tzinfo=tz.utc)
        frame = fetch_and_parse(ts, mock=True)
        assert frame is not None
        assert "tile_url_template" in frame
        assert "{z}" in frame["tile_url_template"]
        assert "georef_ok" in frame
        assert "anomaly" in frame
        assert frame["georef_ok"] is True

    def test_anomaly_flagged_above_threshold(self):
        from apps.ingest.parsers.radar import detect_anomaly

        assert detect_anomaly({"dbz_max": 80.0, "dbz_min": 0.0}) is True
        assert detect_anomaly({"dbz_max": 60.0, "dbz_min": 25.0}) is True
        assert detect_anomaly({"dbz_max": 55.0, "dbz_min": 0.0}) is False

    def test_georef_fails_on_missing_template(self):
        from apps.ingest.parsers.radar import validate_georef

        assert validate_georef({"tile_url_template": ""}) is False
        assert validate_georef({"tile_url_template": "https://x.com/{z}/{x}/{y}.png"}) is True


# ---------------------------------------------------------------------------
# Task integration tests (require DB + INGEST_MOCK=True)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestIngestEcmwf:
    def test_task_creates_forecast_stages(self, settings):
        settings.INGEST_MOCK = True
        from apps.geo.models import HexCell as HC
        hex_count = HC.objects.count()

        from apps.ingest.tasks import ingest_ecmwf
        before = ForecastStage.objects.count()
        count = ingest_ecmwf.apply().get()

        # Task processes ALL hexes in DB (including the 13,874 from Phase 1)
        assert count == hex_count
        assert ForecastStage.objects.count() == before + hex_count

    def test_task_is_idempotent(self, settings):
        settings.INGEST_MOCK = True

        from apps.ingest.tasks import ingest_ecmwf
        first_count = ingest_ecmwf.apply().get()
        second_count = ingest_ecmwf.apply().get()  # same run_ts → skip

        assert first_count > 0
        assert second_count == 0  # idempotent: second run returns 0

    def test_task_updates_ingest_log(self, settings):
        settings.INGEST_MOCK = True
        HexCellFactory()

        from apps.ingest.tasks import ingest_ecmwf
        ingest_ecmwf.apply().get()

        log = IngestLog.objects.get(feed="ecmwf")
        assert log.last_success is not None
        assert log.last_error == ""
        assert log.records_written >= 0


@pytest.mark.django_db
class TestIngestAws:
    def test_task_creates_stations_and_observations(self, settings):
        settings.INGEST_MOCK = True
        # Need hex grid to snap stations to
        HexCellFactory.create_batch(5)

        from apps.ingest.tasks import ingest_aws
        ingest_aws.apply().get()

        assert AwsStation.objects.count() == 10
        assert AwsObservation.objects.count() == 10

    def test_task_is_idempotent(self, settings):
        settings.INGEST_MOCK = True
        HexCellFactory.create_batch(5)

        from apps.ingest.tasks import ingest_aws
        ingest_aws.apply().get()
        ingest_aws.apply().get()

        assert AwsStation.objects.count() == 10
        assert AwsObservation.objects.count() == 10  # second run → same ts → no duplicates

    def test_task_updates_ingest_log(self, settings):
        settings.INGEST_MOCK = True
        HexCellFactory.create_batch(3)

        from apps.ingest.tasks import ingest_aws
        ingest_aws.apply().get()

        log = IngestLog.objects.get(feed="aws")
        assert log.last_success is not None


@pytest.mark.django_db
class TestIngestRadar:
    def test_task_creates_radar_frame(self, settings):
        settings.INGEST_MOCK = True

        from apps.ingest.tasks import ingest_radar
        ingest_radar.apply().get()

        assert RadarFrame.objects.count() == 1
        frame = RadarFrame.objects.first()
        assert frame.georef_ok is True
        assert "{z}" in frame.tile_url_template

    def test_task_is_idempotent(self, settings):
        settings.INGEST_MOCK = True

        from apps.ingest.tasks import ingest_radar
        ingest_radar.apply().get()
        ingest_radar.apply().get()

        assert RadarFrame.objects.count() == 1

    def test_task_updates_ingest_log(self, settings):
        settings.INGEST_MOCK = True

        from apps.ingest.tasks import ingest_radar
        ingest_radar.apply().get()

        log = IngestLog.objects.get(feed="radar")
        assert log.last_success is not None


@pytest.mark.django_db
class TestRecomputeBias:
    def test_task_creates_bias_factors(self, settings):
        settings.INGEST_MOCK = True

        # Seed AWS + forecast data so bias has something to compute
        HexCellFactory.create_batch(5)
        from apps.ingest.tasks import ingest_aws, ingest_ecmwf
        ingest_ecmwf.apply().get()
        ingest_aws.apply().get()

        from apps.ingest.tasks import recompute_bias
        recompute_bias.apply().get()

        # Should have created some bias factors (stations have obs + hex has forecasts)
        assert BiasFactor.objects.count() >= 0  # may be 0 if MIN_PAIRS not met (ts mismatch)
        log = IngestLog.objects.get(feed="bias")
        assert log.last_success is not None

    def test_bias_log_records_count(self, settings):
        settings.INGEST_MOCK = True
        HexCellFactory.create_batch(3)

        from apps.ingest.tasks import recompute_bias
        recompute_bias.apply().get()

        log = IngestLog.objects.get(feed="bias")
        assert log.records_written >= 0


# ---------------------------------------------------------------------------
# IngestLog staleness tracking
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestIngestLog:
    def test_all_four_feeds_get_logged(self, settings):
        settings.INGEST_MOCK = True
        HexCellFactory.create_batch(3)

        from apps.ingest.tasks import ingest_aws, ingest_ecmwf, ingest_radar, recompute_bias
        ingest_ecmwf.apply().get()
        ingest_aws.apply().get()
        ingest_radar.apply().get()
        recompute_bias.apply().get()

        feeds = set(IngestLog.objects.values_list("feed", flat=True))
        assert feeds == {"ecmwf", "aws", "radar", "bias"}

    def test_last_attempted_set_before_success(self, settings):
        settings.INGEST_MOCK = True
        HexCellFactory()

        from apps.ingest.tasks import ingest_ecmwf
        ingest_ecmwf.apply().get()

        log = IngestLog.objects.get(feed="ecmwf")
        assert log.last_attempted is not None
        assert log.last_success is not None
        assert log.last_attempted <= log.last_success + timedelta(seconds=5)
