"""risk/views.py — /risk/hexes, /risk/location, /risk/overview endpoints."""
import json
import logging

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
    """Return (last_success_ts, is_fresh).

    Fail-open policy: as long as *any* RiskSnapshot rows exist we serve the
    latest data and report `fresh=True` — a temporarily paused ingest scheduler
    shouldn't blank out the mobile UI when the DB is full of usable snapshots.
    Only when the DB is genuinely empty (fresh install, never-run pipeline) do
    we surface the "no live data" 503 so the user knows the app isn't broken.
    """
    from apps.ingest.models import IngestLog
    log = IngestLog.objects.filter(feed="ecmwf").first()
    last_success = log.last_success if log else None
    # If we have snapshots on file, serve them — the mobile UI's "no live data"
    # empty state is worse UX than showing a slightly-old-but-real forecast.
    if RiskSnapshot.objects.exists():
        return last_success or _latest_ts(), True
    return last_success, False


# ── GET /risk/hexes?bbox=min_lng,min_lat,max_lng,max_lat&ts= ─────────────────

@api_view(["GET"])
@permission_classes([AllowAny])
def risk_hexes(request):
    """
    GeoJSON FeatureCollection of hex cells with their current risk level.
    Filters by bbox (required) and optionally by ts.

    Wide bboxes (whole-state view) aggregate up to a coarser H3 parent
    resolution so full coverage of TG + AP is visible without a 20 MB payload;
    zoomed-in views serve raw res-7 cells. Cached 60s per bbox+ts+res combo.
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

    # Pick an H3 aggregation resolution based on the viewport span. Res-7 has
    # ~1.2 km edges (~51k cells for TG+AP); res-6 ~3.2 km (~19k); res-5 ~8.5 km
    # (~2.7k). The region view (span > 2°) needs res 5 to render coverage
    # continuously; mid-zoom uses res 6; street level uses raw res 7.
    span = max(max_lng - min_lng, max_lat - min_lat)
    src_res = settings.H3_RESOLUTION  # 7
    if span > 2.0:
        target_res = 5
    elif span > 0.6:
        target_res = 6
    else:
        target_res = src_res

    cache_key = f"risk_hexes:{bbox_str}:{ts_str}:r{target_res}"
    cached = cache.get(cache_key)
    if cached is not None:
        return Response(cached)

    bbox_poly = Polygon.from_bbox((min_lng, min_lat, max_lng, max_lat))

    if target_res == src_res:
        data = _hexes_raw(ts, bbox_poly)
    else:
        data = _hexes_aggregated(ts, bbox_poly, target_res, src_res)

    cache.set(cache_key, data, timeout=60)
    return Response(data)


def _hexes_raw(ts, bbox_poly):
    """Return raw res-7 hex features inside bbox. Bounded by MAX_FEATURES with
    highest-risk cells prioritised so SEVERE/HIGH are never dropped."""
    from django.db.models import Case, When, IntegerField, Value
    RISK_ORDER = Case(
        When(risk_level="SEVERE",   then=Value(4)),
        When(risk_level="HIGH",     then=Value(3)),
        When(risk_level="MODERATE", then=Value(2)),
        When(risk_level="LOW",      then=Value(1)),
        default=Value(0),
        output_field=IntegerField(),
    )
    MAX_FEATURES = 8000

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
                "rain_1h": round(snap.rain_1h or 0.0, 2),
                "rain_24h": round(snap.rain_24h or 0.0, 2),
            },
        })
    return {"type": "FeatureCollection", "features": features}


def _hexes_aggregated(ts, bbox_poly, target_res, src_res):
    """Roll res-7 snapshots up to `target_res` parent cells so the whole-region
    view still shows continuous coverage. Each parent inherits the worst
    risk_level of its children (max of LEVEL_ORDER), and rain values are
    averaged. Polygon geometry is generated from h3.cell_to_boundary."""
    rows = (
        RiskSnapshot.objects
        .filter(ts=ts, hex__centroid__within=bbox_poly)
        .values_list("hex__h3_index", "risk_level", "hazard_class",
                     "confidence", "rain_1h", "rain_24h")
    )

    groups = {}
    for h3_idx, risk, hazard, conf, r1, r24 in rows:
        parent = h3.cell_to_parent(h3_idx, target_res)
        g = groups.get(parent)
        if g is None:
            g = {"risk": risk, "hazard": hazard, "conf_sum": 0, "n": 0,
                 "r1_sum": 0.0, "r24_sum": 0.0, "risk_ord": LEVEL_ORDER.get(risk, 0)}
            groups[parent] = g
        this_ord = LEVEL_ORDER.get(risk, 0)
        if this_ord > g["risk_ord"]:
            g["risk"] = risk
            g["hazard"] = hazard
            g["risk_ord"] = this_ord
        g["conf_sum"] += conf or 0
        g["r1_sum"] += r1 or 0.0
        g["r24_sum"] += r24 or 0.0
        g["n"] += 1

    features = []
    for parent, g in groups.items():
        # h3.cell_to_boundary returns (lat, lng) tuples; GeoJSON wants (lng, lat)
        boundary = h3.cell_to_boundary(parent)
        ring = [[lng, lat] for lat, lng in boundary]
        # Close the ring for GeoJSON polygon validity.
        ring.append(ring[0])
        n = g["n"] or 1
        features.append({
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [ring]},
            "properties": {
                "h3_index": parent,
                "risk_level": g["risk"],
                "hazard_class": g["hazard"],
                "confidence": round(g["conf_sum"] / n),
                "rain_1h": round(g["r1_sum"] / n, 2),
                "rain_24h": round(g["r24_sum"] / n, 2),
            },
        })
    return {"type": "FeatureCollection", "features": features}


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
