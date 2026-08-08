"""risk/views.py — /risk/hexes, /risk/location, /risk/overview endpoints."""
import json
import logging
from datetime import timedelta

import h3
from django.conf import settings
from django.contrib.gis.db.models.functions import AsGeoJSON
from django.contrib.gis.geos import Polygon
from django.core.cache import cache
from django.db.models import Avg, Count, Max
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.geo.models import HexCell
from apps.risk.models import RiskSnapshot
from apps.risk.plain_text import generate as plain_text_generate

logger = logging.getLogger("floodguard.risk")

LEVEL_ORDER = {"LOW": 0, "MODERATE": 1, "HIGH": 2, "SEVERE": 3}


def _latest_ts():
    return RiskSnapshot.objects.aggregate(Max("ts"))["ts__max"]


def _stale_response(ts):
    """Return a 503 payload signalling that no fresh risk data is available.
    Explicit signal to the client so it can show 'no live data' instead of stale values."""
    return Response(
        {
            "detail": "No live forecast data available. The upstream weather feed is not reporting.",
            "code": "STALE_FORECAST",
            "last_update": ts.isoformat() if ts else None,
            "max_age_hours": getattr(settings, "RISK_FRESHNESS_HOURS", 2),
        },
        status=503,
    )


def _freshness_check():
    """Return (last_success_ts, is_fresh) based on when the forecast feed last
    landed data. RiskSnapshot.ts points at a future hour (when the risk applies),
    so it can't be used to detect staleness — we track the ingest itself.
    Returns (None, False) if the feed has never succeeded."""
    from apps.ingest.models import IngestLog
    max_age = timedelta(hours=getattr(settings, "RISK_FRESHNESS_HOURS", 2))
    log = IngestLog.objects.filter(feed="ecmwf").first()
    if not log or not log.last_success:
        return None, False
    return log.last_success, (timezone.now() - log.last_success) <= max_age


# ── GET /risk/hexes?bbox=min_lng,min_lat,max_lng,max_lat&ts= ─────────────────

@api_view(["GET"])
@permission_classes([AllowAny])
def risk_hexes(request):
    """
    GeoJSON FeatureCollection of hex cells with their current risk level.
    Filters by bbox (required) and optionally by ts.
    Lean response: only h3_index, risk_level, hazard_class, confidence in properties.
    Cached 60s per bbox+ts combination.
    """
    bbox_str = request.query_params.get("bbox", "")
    ts_str = request.query_params.get("ts", "")

    if not bbox_str:
        return Response({"detail": "bbox is required: min_lng,min_lat,max_lng,max_lat"}, status=400)

    try:
        min_lng, min_lat, max_lng, max_lat = map(float, bbox_str.split(","))
    except (ValueError, TypeError):
        return Response({"detail": "Invalid bbox format. Use: min_lng,min_lat,max_lng,max_lat"}, status=400)

    # Freshness gate first — before cache — so a stale feed always surfaces.
    # Explicit ?ts= (admin backfill) bypasses the gate.
    if ts_str:
        from django.utils.dateparse import parse_datetime
        ts = parse_datetime(ts_str) or _latest_ts()
    else:
        last_success, fresh = _freshness_check()
        if not fresh:
            return _stale_response(last_success)
        ts = _latest_ts()

    if ts is None:
        return _stale_response(None)

    cache_key = f"risk_hexes:{bbox_str}:{ts_str}"
    cached = cache.get(cache_key)
    if cached is not None:
        return Response(cached)

    bbox_poly = Polygon.from_bbox((min_lng, min_lat, max_lng, max_lat))

    # Cap payload for wide bboxes (e.g. whole-region view fits ~51k hexes,
    # ~10 MB GeoJSON — browsers can't render that smoothly). We order so the
    # highest-risk cells always survive the cap, then let the remainder fill
    # up to MAX_FEATURES. On a dry day (all LOW) this returns a representative
    # top-K sample; on an active day every SEVERE/HIGH cell is guaranteed.
    from django.db.models import Case, When, IntegerField, Value
    RISK_ORDER = Case(
        When(risk_level="SEVERE",   then=Value(4)),
        When(risk_level="HIGH",     then=Value(3)),
        When(risk_level="MODERATE", then=Value(2)),
        When(risk_level="LOW",      then=Value(1)),
        default=Value(0),
        output_field=IntegerField(),
    )
    MAX_FEATURES = 5000

    snapshots = (
        RiskSnapshot.objects
        .filter(ts=ts, hex__centroid__within=bbox_poly)
        .select_related("hex")
        .annotate(geojson=AsGeoJSON("hex__geom"), risk_order=RISK_ORDER)
        .only("risk_level", "hazard_class", "confidence",
              "rain_1h", "rain_24h", "hex__h3_index")
        .order_by("-risk_order", "-confidence", "hex__h3_index")[:MAX_FEATURES]
    )

    features = []
    for snap in snapshots:
        if not snap.geojson:
            continue
        features.append({
            "type": "Feature",
            "geometry": json.loads(snap.geojson),
            "properties": {
                "h3_index": snap.hex_id,
                "risk_level": snap.risk_level,
                "hazard_class": snap.hazard_class,
                "confidence": snap.confidence,
                # Rainfall values so the mobile map can render a rain-intensity
                # choropleth without a second API round-trip.
                "rain_1h": round(snap.rain_1h or 0.0, 2),
                "rain_24h": round(snap.rain_24h or 0.0, 2),
            },
        })

    data = {"type": "FeatureCollection", "features": features}
    cache.set(cache_key, data, timeout=60)
    return Response(data)


# ── GET /risk/location?lat=&lng= ─────────────────────────────────────────────

@api_view(["GET"])
@permission_classes([AllowAny])
def risk_location(request):
    """
    Snap lat/lng to nearest H3 res-9 hex, return current risk + 24-hour strip
    + plain-language text + confidence.
    """
    try:
        lat = float(request.query_params["lat"])
        lng = float(request.query_params["lng"])
    except (KeyError, ValueError, TypeError):
        return Response({"detail": "lat and lng are required float parameters."}, status=400)

    h3_index = h3.latlng_to_cell(lat, lng, settings.H3_RESOLUTION)

    try:
        cell = HexCell.objects.get(h3_index=h3_index)
    except HexCell.DoesNotExist:
        return Response({"detail": "Location is outside the covered area."}, status=404)

    # City-wide freshness gate — if the whole system has no fresh data, don't lie
    # about this location either.
    global_ts, fresh = _freshness_check()
    if not fresh:
        return _stale_response(global_ts)

    latest = (
        RiskSnapshot.objects
        .filter(hex=cell)
        .order_by("-ts")
        .first()
    )

    if not latest:
        return _stale_response(global_ts)

    plain_text, advice = plain_text_generate(latest.risk_level, latest.hazard_class)

    # 24-hour strip (most recent 24 snapshots)
    hourly_qs = (
        RiskSnapshot.objects
        .filter(hex=cell)
        .order_by("-ts")
        .values("ts", "risk_level", "rain_1h", "confidence")[:24]
    )
    hourly = [
        {"ts": s["ts"].isoformat(), "risk_level": s["risk_level"],
         "rain_1h": s["rain_1h"], "confidence": s["confidence"]}
        for s in hourly_qs
    ]

    return Response({
        "h3_index": h3_index,
        "ward_name": cell.ward_name or None,
        "risk_level": latest.risk_level,
        "hazard_class": latest.hazard_class,
        "rain_1h": latest.rain_1h,
        "rain_3h": latest.rain_3h,
        "rain_24h": latest.rain_24h,
        "plain_text": plain_text,
        "advice": advice,
        "explanation": latest.risk_level and f"{plain_text}. {advice}",
        "confidence": latest.confidence,
        "ts": latest.ts.isoformat(),
        "hourly": hourly,
    })


# ── GET /risk/overview ────────────────────────────────────────────────────────

@api_view(["GET"])
@permission_classes([AllowAny])
def risk_overview(request):
    """
    City-level aggregates:
      forecast_rain_24h, max_rate_1h, confidence,
      summary {severe%, high%, moderate%, low%},
      hotspots [top 5 SEVERE/HIGH hexes]
    """
    # Freshness gate before cache
    last_success, fresh = _freshness_check()
    if not fresh:
        return _stale_response(last_success)

    cache_key = "risk_overview"
    cached = cache.get(cache_key)
    if cached is not None:
        return Response(cached)

    ts = _latest_ts()
    if ts is None:
        return _stale_response(last_success)

    snapshots = RiskSnapshot.objects.filter(ts=ts)
    total = snapshots.count()

    if total == 0:
        return _stale_response(last_success)

    # Aggregate counts per level
    counts = dict(snapshots.values_list("risk_level").annotate(cnt=Count("id")).values_list("risk_level", "cnt"))
    aggs = snapshots.aggregate(
        avg_rain_24h=Avg("rain_24h"),
        max_rain_1h=Max("rain_1h"),
        avg_conf=Avg("confidence"),
    )

    def pct(level):
        return round(counts.get(level, 0) / total * 100, 1)

    # Top hotspots — SEVERE first, then HIGH, ordered by rain_1h desc
    hotspot_qs = (
        RiskSnapshot.objects
        .filter(ts=ts, risk_level__in=["SEVERE", "HIGH"])
        .select_related("hex")
        .order_by("-rain_1h")[:5]
    )
    hotspots = [
        {
            "h3_index": s.hex_id,
            "risk_level": s.risk_level,
            "rain_1h": s.rain_1h,
            "ward_name": s.hex.ward_name or s.hex_id,
            "lat": s.hex.centroid.y if s.hex.centroid else None,
            "lng": s.hex.centroid.x if s.hex.centroid else None,
        }
        for s in hotspot_qs
    ]

    data = {
        "ts": ts.isoformat(),
        "forecast_rain_24h": round(aggs["avg_rain_24h"] or 0, 2),
        "max_rate_1h": round(aggs["max_rain_1h"] or 0, 2),
        "confidence": round(aggs["avg_conf"] or 0),
        "total_hexes": total,
        "summary": {
            "severe":   pct("SEVERE"),
            "high":     pct("HIGH"),
            "moderate": pct("MODERATE"),
            "low":      pct("LOW"),
        },
        "hotspots": hotspots,
    }
    cache.set(cache_key, data, timeout=60)
    return Response(data)


# ── GET /risk/hourly-forecast ─────────────────────────────────────────────────

REGION_CENTROID = (16.5000, 80.0000)  # Vijayawada area — centre of TG + AP union
# Legacy alias kept until every caller uses REGION_CENTROID.
HYD_CENTROID = REGION_CENTROID
OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


@api_view(["GET"])
@permission_classes([AllowAny])
def hourly_forecast(request):
    """
    48-hour hourly precipitation forecast for the Hyderabad centroid.
    Pulled live from Open-Meteo (no API key). Cached 5 min server-side to
    respect Open-Meteo's rate limits and keep response fast.

    Returns:
      { generated_at, hours: [{ts, rain_mm}, ...] }
    Or 503 if Open-Meteo is unreachable.
    """
    import requests

    cache_key = "hourly_forecast_v1"
    cached = cache.get(cache_key)
    if cached is not None:
        return Response(cached)

    try:
        resp = requests.get(
            OPEN_METEO_FORECAST_URL,
            params={
                "latitude": HYD_CENTROID[0],
                "longitude": HYD_CENTROID[1],
                "hourly": "precipitation",
                "forecast_days": 3,
                "timezone": "UTC",
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.error("hourly_forecast: Open-Meteo unreachable: %s", exc)
        return Response(
            {
                "detail": "Live forecast source is not reachable.",
                "code": "FORECAST_UPSTREAM_DOWN",
            },
            status=503,
        )

    hourly = data.get("hourly") or {}
    times = hourly.get("time") or []
    precip = hourly.get("precipitation") or []

    now_iso = timezone.now().strftime("%Y-%m-%dT%H:%M")
    hours = []
    for t, p in zip(times, precip):
        if t < now_iso:
            continue
        hours.append({
            "ts": t,
            "rain_mm": round(float(p or 0.0), 3),
        })
        if len(hours) >= 48:
            break

    payload = {
        "generated_at": timezone.now().isoformat(),
        "hours": hours,
    }
    cache.set(cache_key, payload, timeout=300)
    return Response(payload)


# ── GET /risk/weather-now ─────────────────────────────────────────────────────

@api_view(["GET"])
@permission_classes([AllowAny])
def weather_now(request):
    """
    Current-conditions snapshot for the Hyderabad centroid pulled live from
    Open-Meteo. Cached 5 min. Returns 503 if upstream is unreachable.

    Fields:
      temperature_c, humidity_pct, wind_kmh, wind_dir_deg, weather_code
    plus a human-friendly `description` derived from the WMO weather code.
    """
    import requests

    cache_key = "weather_now_v1"
    cached = cache.get(cache_key)
    if cached is not None:
        return Response(cached)

    try:
        resp = requests.get(
            OPEN_METEO_FORECAST_URL,
            params={
                "latitude": HYD_CENTROID[0],
                "longitude": HYD_CENTROID[1],
                "current": (
                    "temperature_2m,relative_humidity_2m,"
                    "wind_speed_10m,wind_direction_10m,weather_code"
                ),
                "timezone": "UTC",
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.error("weather_now: Open-Meteo unreachable: %s", exc)
        return Response(
            {"detail": "Live weather source is not reachable.",
             "code": "WEATHER_UPSTREAM_DOWN"},
            status=503,
        )

    cur = data.get("current") or {}
    code = int(cur.get("weather_code") or 0)

    payload = {
        "generated_at": timezone.now().isoformat(),
        "observed_at": cur.get("time"),
        "temperature_c": round(float(cur.get("temperature_2m") or 0), 1),
        "humidity_pct": int(cur.get("relative_humidity_2m") or 0),
        "wind_kmh": round(float(cur.get("wind_speed_10m") or 0), 1),
        "wind_dir_deg": int(cur.get("wind_direction_10m") or 0),
        "weather_code": code,
        "description": _wmo_description(code),
    }
    cache.set(cache_key, payload, timeout=300)
    return Response(payload)


# WMO weather codes → concise human-readable descriptions.
# Reference: https://open-meteo.com/en/docs#weathervariables
_WMO_DESCRIPTIONS = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Rime fog",
    51: "Light drizzle",
    53: "Drizzle",
    55: "Heavy drizzle",
    56: "Freezing drizzle",
    57: "Freezing drizzle",
    61: "Light rain",
    63: "Rain",
    65: "Heavy rain",
    66: "Freezing rain",
    67: "Freezing rain",
    71: "Light snow",
    73: "Snow",
    75: "Heavy snow",
    77: "Snow grains",
    80: "Rain showers",
    81: "Rain showers",
    82: "Violent rain showers",
    85: "Snow showers",
    86: "Snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with hail",
    99: "Thunderstorm with hail",
}


def _wmo_description(code: int) -> str:
    return _WMO_DESCRIPTIONS.get(code, "Unknown")
