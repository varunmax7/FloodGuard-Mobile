"""
Bias factor computation.

For each AwsStation compares trailing-window AwsObservation (observed)
against ForecastStage (predicted) for the station's hex.

multiplier = mean(observed_1h) / mean(predicted_1h)   clamped [0.1, 10.0]
offset     = 0  (additive correction reserved for Phase 12 calibration UI)
"""
import logging
from datetime import timedelta

import numpy as np

logger = logging.getLogger("floodguard.ingest.bias")

TRAILING_HOURS = 72
MIN_PAIRS = 3       # need at least this many matched (obs, pred) pairs
CLAMP_LOW = 0.1
CLAMP_HIGH = 10.0


def compute_for_station(station_id: str, trailing_hours: int = TRAILING_HOURS):
    """Return (multiplier, offset) or (1.0, 0.0) if insufficient data."""
    from apps.geo.models import AwsObservation, AwsStation
    from apps.ingest.models import ForecastStage
    from django.utils import timezone

    cutoff = timezone.now() - timedelta(hours=trailing_hours)

    try:
        station = AwsStation.objects.select_related("hex").get(station_id=station_id)
    except AwsStation.DoesNotExist:
        return 1.0, 0.0

    if not station.hex_id:
        return 1.0, 0.0

    obs_qs = (
        AwsObservation.objects
        .filter(station=station, ts__gte=cutoff)
        .values_list("rain_1h", flat=True)
    )
    pred_qs = (
        ForecastStage.objects
        .filter(hex_id=station.hex_id, valid_ts__gte=cutoff)
        .values_list("rain_1h", flat=True)
    )

    obs = np.array([v for v in obs_qs if v is not None], dtype=float)
    pred = np.array([v for v in pred_qs if v is not None], dtype=float)

    if len(obs) < MIN_PAIRS or len(pred) < MIN_PAIRS:
        logger.debug("Bias skip %s: obs=%d pred=%d (need %d)", station_id, len(obs), len(pred), MIN_PAIRS)
        return 1.0, 0.0

    mean_pred = float(np.mean(pred))
    mean_obs = float(np.mean(obs))

    if mean_pred < 0.01:
        return 1.0, 0.0

    multiplier = float(np.clip(mean_obs / mean_pred, CLAMP_LOW, CLAMP_HIGH))
    return round(multiplier, 4), 0.0


def recompute_all(trailing_hours: int = TRAILING_HOURS) -> int:
    """Recompute and persist BiasFactor for every station with recent observations."""
    from apps.geo.models import AwsStation
    from apps.risk.models import BiasFactor
    from django.utils import timezone

    cutoff = timezone.now() - timedelta(hours=trailing_hours)
    stations = AwsStation.objects.filter(observations__ts__gte=cutoff).distinct()

    count = 0
    for station in stations:
        multiplier, offset = compute_for_station(station.station_id, trailing_hours)
        BiasFactor.objects.create(
            station_id=station.station_id,
            region="",
            multiplier=multiplier,
            offset=offset,
            valid_from=timezone.now(),
        )
        logger.debug("BiasFactor %s: multiplier=%.4f", station.station_id, multiplier)
        count += 1

    return count
