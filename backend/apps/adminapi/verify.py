"""adminapi/verify.py — §2.1 Forecast Verification endpoints."""
import math
from datetime import timedelta

from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from .permissions import IsStaffAny


def _mae(pairs):
    if not pairs:
        return None
    return round(sum(abs(p - o) for p, o in pairs) / len(pairs), 3)


def _bias(pairs):
    if not pairs:
        return None
    return round(sum(p - o for p, o in pairs) / len(pairs), 3)


def _corr(pairs):
    n = len(pairs)
    if n < 2:
        return None
    px = [p for p, _ in pairs]
    ox = [o for _, o in pairs]
    mx, mo = sum(px) / n, sum(ox) / n
    num = sum((p - mx) * (o - mo) for p, o in pairs)
    den = math.sqrt(sum((p - mx) ** 2 for p in px) * sum((o - mo) ** 2 for o in ox))
    return round(num / den, 4) if den else None


# ── Station list ──────────────────────────────────────────────────────────────

@api_view(["GET"])
@permission_classes([IsStaffAny])
def station_list(request):
    """GET /api/v1/admin/verify/stations/ — list all AWS stations."""
    from apps.geo.models import AwsStation
    stations = list(AwsStation.objects.values("station_id", "name"))
    return Response(stations)


# ── §2.1a: per-station timeseries ─────────────────────────────────────────────

@api_view(["GET"])
@permission_classes([IsStaffAny])
def station_timeseries(request, station_id):
    """
    GET /api/v1/admin/verify/stations/{id}/timeseries/?window=72
    Returns aligned predicted-vs-observed series + metrics + bias factor.
    """
    from apps.geo.models import AwsStation, AwsObservation
    from apps.ingest.models import ForecastStage
    from apps.risk.models import BiasFactor

    window_h = int(request.query_params.get("window", 72))
    since = timezone.now() - timedelta(hours=window_h)

    try:
        station = AwsStation.objects.select_related("hex").get(station_id=station_id)
    except AwsStation.DoesNotExist:
        return Response({"detail": "Station not found."}, status=404)

    obs_map = {
        o["ts"].isoformat(): o
        for o in AwsObservation.objects.filter(station=station, ts__gte=since)
        .order_by("ts")
        .values("ts", "rain_1h", "rain_3h", "rain_24h")
    }

    pred_map = {}
    if station.hex_id:
        pred_map = {
            p["valid_ts"].isoformat(): p
            for p in ForecastStage.objects.filter(hex_id=station.hex_id, valid_ts__gte=since)
            .order_by("valid_ts")
            .values("valid_ts", "rain_1h", "rain_3h", "rain_24h")
        }

    all_ts = sorted(set(obs_map) | set(pred_map))
    series = [
        {
            "ts": t,
            "obs_1h":  obs_map.get(t, {}).get("rain_1h"),
            "pred_1h": pred_map.get(t, {}).get("rain_1h"),
            "obs_3h":  obs_map.get(t, {}).get("rain_3h"),
            "pred_3h": pred_map.get(t, {}).get("rain_3h"),
            "obs_24h": obs_map.get(t, {}).get("rain_24h"),
            "pred_24h":pred_map.get(t, {}).get("rain_24h"),
        }
        for t in all_ts
    ]

    p1 = [(r["pred_1h"], r["obs_1h"]) for r in series if r["pred_1h"] is not None and r["obs_1h"] is not None]
    p3 = [(r["pred_3h"], r["obs_3h"]) for r in series if r["pred_3h"] is not None and r["obs_3h"] is not None]

    bf = BiasFactor.objects.filter(station_id=station_id).order_by("-valid_from").first()

    return Response({
        "station": {"id": station.station_id, "name": station.name},
        "window_h": window_h,
        "series": series,
        "metrics": {
            "mae_1h":  _mae(p1), "bias_1h": _bias(p1), "corr_1h": _corr(p1),
            "mae_3h":  _mae(p3), "bias_3h": _bias(p3), "corr_3h": _corr(p3),
            "n": len(p1),
        },
        "bias_factor": {
            "multiplier": bf.multiplier if bf else 1.0,
            "offset":     bf.offset     if bf else 0.0,
            "valid_from": bf.valid_from.isoformat() if bf else None,
        },
    })


# ── §2.1b: per-station error metrics ──────────────────────────────────────────

@api_view(["GET"])
@permission_classes([IsStaffAny])
def error_metrics(request):
    """GET /api/v1/admin/verify/errors/?window=72 — MAE/bias/corr for all stations."""
    from apps.geo.models import AwsStation, AwsObservation
    from apps.ingest.models import ForecastStage

    window_h = int(request.query_params.get("window", 72))
    since = timezone.now() - timedelta(hours=window_h)

    result = []
    for station in AwsStation.objects.filter(hex__isnull=False).select_related("hex")[:50]:
        obs_map = {
            o["ts"]: o["rain_1h"]
            for o in AwsObservation.objects.filter(station=station, ts__gte=since).values("ts", "rain_1h")
        }
        pred_map = {
            p["valid_ts"]: p["rain_1h"]
            for p in ForecastStage.objects.filter(hex_id=station.hex_id, valid_ts__gte=since)
            .values("valid_ts", "rain_1h")
        }
        pairs = [
            (pred_map[t], obs_map[t])
            for t in set(obs_map) & set(pred_map)
            if pred_map.get(t) is not None and obs_map.get(t) is not None
        ]
        result.append({
            "station_id": station.station_id,
            "name": station.name,
            "mae":  _mae(pairs),
            "bias": _bias(pairs),
            "corr": _corr(pairs),
            "n":    len(pairs),
        })

    return Response(result)


# ── §2.1c: spatial error map ──────────────────────────────────────────────────

@api_view(["GET"])
@permission_classes([IsStaffAny])
def error_map(request):
    """GET /api/v1/admin/verify/error-map/ — GeoJSON FeatureCollection of predicted-observed diffs."""
    from apps.geo.models import AwsStation, AwsObservation
    from apps.ingest.models import ForecastStage

    window_h = int(request.query_params.get("window", 24))
    since = timezone.now() - timedelta(hours=window_h)

    features = []
    for station in AwsStation.objects.filter(hex__isnull=False).select_related("hex"):
        obs  = AwsObservation.objects.filter(station=station, ts__gte=since).order_by("-ts").first()
        pred = ForecastStage.objects.filter(hex_id=station.hex_id, valid_ts__gte=since).order_by("-valid_ts").first()
        if not obs or not pred or not station.hex.centroid:
            continue
        diff = (pred.rain_1h or 0) - (obs.rain_1h or 0)
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [station.hex.centroid.x, station.hex.centroid.y],
            },
            "properties": {
                "station_id": station.station_id,
                "h3_index":   station.hex_id,
                "pred_1h":    pred.rain_1h,
                "obs_1h":     obs.rain_1h,
                "diff_1h":    round(diff, 3),
                "ts":         obs.ts.isoformat(),
            },
        })

    return Response({"type": "FeatureCollection", "features": features})
