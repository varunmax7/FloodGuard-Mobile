"""
Celery ingest tasks — ECMWF forecast, AWS observations, radar frames, bias recompute.

All tasks:
  - update IngestLog.last_attempted on entry
  - update IngestLog.last_success + records_written on success
  - store exception text in IngestLog.last_error on failure
  - are idempotent (same run_ts/ts → no duplicates)
"""
import logging

from celery import shared_task
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger("floodguard.ingest")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _log_start(feed: str):
    from apps.ingest.models import IngestLog
    log, _ = IngestLog.objects.get_or_create(feed=feed)
    log.last_attempted = timezone.now()
    log.save(update_fields=["last_attempted"])
    return log


def _log_success(log, records: int):
    log.last_success = timezone.now()
    log.records_written = records
    log.last_error = ""
    log.save(update_fields=["last_success", "records_written", "last_error"])


def _log_error(log, exc: Exception):
    log.last_error = str(exc)[:2000]
    log.save(update_fields=["last_error"])


# ── ECMWF forecast ingest (hourly) ────────────────────────────────────────────

@shared_task(
    bind=True,
    name="apps.ingest.tasks.ingest_ecmwf",
    max_retries=3,
    default_retry_delay=120,
)
def ingest_ecmwf(self):
    """
    Sample ECMWF total precipitation at every HexCell centroid for the current
    model run, and upsert into ForecastStage.
    """
    from django.conf import settings
    from apps.geo.models import HexCell
    from apps.ingest.models import ForecastStage
    from apps.ingest.parsers import ecmwf as parser

    log = _log_start("ecmwf")
    try:
        # FORECAST_LIVE overrides the global mock flag for just this feed.
        mock = getattr(settings, "INGEST_MOCK", True) and not getattr(settings, "FORECAST_LIVE", False)
        run_ts = timezone.now().replace(minute=0, second=0, microsecond=0)

        # Skip if this run_ts was already ingested (either legacy ECMWF-tagged rows
        # or new OPEN_METEO rows both count — one forecast per run_ts hour is enough)
        if ForecastStage.objects.filter(run_ts=run_ts, source__in=["ECMWF", "OPEN_METEO"]).exists():
            logger.info("Forecast: run_ts=%s already staged, skipping", run_ts)
            _log_success(log, 0)
            return 0

        hex_cells = list(HexCell.objects.only("h3_index", "centroid"))
        logger.info("Forecast: %d hexes, mock=%s, run_ts=%s", len(hex_cells), mock, run_ts)

        records = parser.fetch_and_parse(run_ts, hex_cells, mock=mock)

        hex_map = {c.h3_index: c for c in hex_cells}
        stages = [
            ForecastStage(
                hex=hex_map[r["hex_id"]],
                valid_ts=r["valid_ts"],
                run_ts=r["run_ts"],
                rain_1h=r["rain_1h"],
                rain_3h=r["rain_3h"],
                rain_24h=r["rain_24h"],
                source=r["source"],
            )
            for r in records
            if r["hex_id"] in hex_map
        ]

        with transaction.atomic():
            ForecastStage.objects.bulk_create(stages, ignore_conflicts=True)

        _log_success(log, len(stages))
        logger.info("ECMWF: %d ForecastStage rows written", len(stages))
        return len(stages)

    except Exception as exc:
        _log_error(log, exc)
        logger.exception("ECMWF ingest failed")
        raise self.retry(exc=exc)


# ── AWS rain gauge ingest (every 15 min) ─────────────────────────────────────

@shared_task(
    bind=True,
    name="apps.ingest.tasks.ingest_aws",
    max_retries=3,
    default_retry_delay=60,
)
def ingest_aws(self):
    """
    Fetch AWS station rainfall observations, auto-create stations snapped to
    their H3 hex, and upsert AwsObservation rows.
    """
    import h3
    from django.conf import settings
    from django.contrib.gis.geos import Point
    from apps.geo.models import AwsObservation, AwsStation, HexCell
    from apps.ingest.parsers import aws as parser

    log = _log_start("aws")
    try:
        # AWS_LIVE overrides the global mock flag; Open-Meteo needs no key.
        mock = getattr(settings, "INGEST_MOCK", True) and not getattr(settings, "AWS_LIVE", False)
        ts = timezone.now().replace(second=0, microsecond=0)

        records = parser.fetch_and_parse(ts, mock=mock)

        created_obs = 0
        for r in records:
            # Upsert station
            h3_index = h3.latlng_to_cell(r["lat"], r["lng"], settings.H3_RESOLUTION)
            hex_cell = HexCell.objects.filter(h3_index=h3_index).first()

            station, _ = AwsStation.objects.get_or_create(
                station_id=r["station_id"],
                defaults={
                    "name": r["name"],
                    "geom": Point(r["lng"], r["lat"], srid=4326),
                    "hex": hex_cell,
                },
            )

            # Upsert observation (idempotent via unique constraint)
            _, created = AwsObservation.objects.get_or_create(
                station=station,
                ts=r["ts"],
                defaults={
                    "rain_1h": r["rain_1h"],
                    "rain_3h": r["rain_3h"],
                    "rain_24h": r["rain_24h"],
                },
            )
            if created:
                created_obs += 1

        _log_success(log, created_obs)
        logger.info("AWS: %d new observations written", created_obs)
        return created_obs

    except Exception as exc:
        _log_error(log, exc)
        logger.exception("AWS ingest failed")
        raise self.retry(exc=exc)


# ── Radar frame ingest (every 10 min) ────────────────────────────────────────

@shared_task(
    bind=True,
    name="apps.ingest.tasks.ingest_radar",
    max_retries=2,
    default_retry_delay=30,
)
def ingest_radar(self):
    """
    Fetch the latest radar frame metadata, validate georef + anomaly,
    and upsert a RadarFrame row.
    """
    from django.conf import settings
    from apps.ingest.models import RadarFrame
    from apps.ingest.parsers import radar as parser

    log = _log_start("radar")
    try:
        # RADAR_LIVE overrides the global mock flag; RainViewer is free/no-key.
        mock = getattr(settings, "INGEST_MOCK", True) and not getattr(settings, "RADAR_LIVE", False)
        ts = timezone.now().replace(second=0, microsecond=0)

        frame = parser.fetch_and_parse(ts, mock=mock)
        if frame is None:
            logger.info("Radar: no new frame available")
            _log_success(log, 0)
            return 0

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

        written = 1 if created else 0
        _log_success(log, written)
        logger.info(
            "Radar: frame ts=%s georef_ok=%s anomaly=%s (%s)",
            frame["ts"], frame["georef_ok"], frame["anomaly"],
            "new" if created else "duplicate",
        )
        return written

    except Exception as exc:
        _log_error(log, exc)
        logger.exception("Radar ingest failed")
        raise self.retry(exc=exc)


# ── Bias recompute (hourly) ───────────────────────────────────────────────────

@shared_task(
    bind=True,
    name="apps.ingest.tasks.recompute_bias",
    max_retries=2,
    default_retry_delay=120,
)
def recompute_bias(self):
    """
    Compute per-station BiasFactor from trailing 72h of (observed vs predicted)
    and persist to risk_bias_factor table.
    """
    from apps.ingest.parsers import bias as parser

    log = _log_start("bias")
    try:
        count = parser.recompute_all()
        _log_success(log, count)
        logger.info("Bias recompute: %d BiasFactor rows written", count)
        return count

    except Exception as exc:
        _log_error(log, exc)
        logger.exception("Bias recompute failed")
        raise self.retry(exc=exc)
