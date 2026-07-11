"""
Risk engine Celery task — reads ForecastStage + BiasFactor → writes RiskSnapshot.
Runs after every ECMWF ingest (hourly at :15).
"""
import logging
from datetime import timedelta

from celery import shared_task
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

logger = logging.getLogger("floodguard.risk")


@shared_task(
    bind=True,
    name="apps.risk.tasks.recompute_all_risk",
    max_retries=3,
    default_retry_delay=120,
)
def recompute_all_risk(self):
    """
    For each hex with a ForecastStage for the latest ECMWF run:
      1. Apply BiasFactor correction
      2. Run risk engine (§3.2)
      3. Upsert RiskSnapshot
    """
    from apps.geo.models import AwsObservation, AwsStation, HexCell
    from apps.ingest.models import ForecastStage
    from apps.risk.engine import compute_risk
    from apps.risk.models import BiasFactor, RiskSnapshot

    try:
        latest_run_ts = ForecastStage.objects.aggregate(Max("run_ts"))["run_ts__max"]
        if not latest_run_ts:
            logger.warning("recompute_all_risk: no ForecastStage rows — skipping")
            return 0

        logger.info("recompute_all_risk: run_ts=%s", latest_run_ts)

        # ── Pre-load bias factors (latest per station) ────────────────────────
        bias_map: dict[str, tuple[float, float]] = {}
        for bf in BiasFactor.objects.order_by("station_id", "-valid_from"):
            if bf.station_id not in bias_map:
                bias_map[bf.station_id] = (bf.multiplier, bf.offset)
        default_bias = bias_map.get("", (1.0, 0.0))

        # ── Map hex → station_id (for bias lookup) ────────────────────────────
        hex_to_station: dict[str, str] = dict(
            AwsStation.objects.filter(hex__isnull=False)
            .values_list("hex_id", "station_id")
        )

        # ── Hexes with recent AWS observations (for confidence boost) ─────────
        obs_cutoff = timezone.now() - timedelta(hours=2)
        hexes_with_obs: set[str] = set(
            AwsObservation.objects.filter(ts__gte=obs_cutoff)
            .values_list("station__hex_id", flat=True)
        )

        # ── Load ForecastStage for latest run ─────────────────────────────────
        # Accept both legacy ECMWF (seeded/mock) and live OPEN_METEO rows.
        stages = list(
            ForecastStage.objects
            .filter(run_ts=latest_run_ts, source__in=["ECMWF", "OPEN_METEO"])
            .select_related("hex")
        )

        logger.info("recompute_all_risk: %d stages to process", len(stages))

        # ── Delete old snapshots for this valid_ts (idempotent) ───────────────
        valid_ts = stages[0].valid_ts if stages else None
        if valid_ts:
            RiskSnapshot.objects.filter(ts=valid_ts).delete()

        # ── Compute and collect RiskSnapshot objects ───────────────────────────
        snapshots = []
        for stage in stages:
            cell = stage.hex
            station_id = hex_to_station.get(cell.h3_index)
            multiplier, offset = bias_map.get(station_id, default_bias) if station_id else default_bias
            has_obs = cell.h3_index in hexes_with_obs

            lead_hours = (
                (stage.valid_ts - stage.run_ts).total_seconds() / 3600
                if stage.valid_ts and stage.run_ts else 1.0
            )

            result = compute_risk(
                rain_raw_1h=stage.rain_1h or 0.0,
                bias_multiplier=multiplier,
                bias_offset=offset,
                fsi_score=cell.fsi_score,
                lead_time_hours=lead_hours,
                has_station_obs=has_obs,
            )

            snapshots.append(RiskSnapshot(
                hex=cell,
                ts=stage.valid_ts,
                rain_1h=result.rain_corrected,
                rain_3h=stage.rain_3h,
                rain_24h=stage.rain_24h,
                hazard_class=result.hazard_class,
                risk_level=result.risk_level,
                confidence=result.confidence,
                source_model="ECMWF",
            ))

        with transaction.atomic():
            RiskSnapshot.objects.bulk_create(snapshots, batch_size=500)

        logger.info("recompute_all_risk: %d RiskSnapshot rows written", len(snapshots))
        return len(snapshots)

    except Exception as exc:
        logger.exception("recompute_all_risk failed")
        raise self.retry(exc=exc)
