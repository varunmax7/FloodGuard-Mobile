"""risk/views.py — /risk/hexes, /risk/location, /risk/overview endpoints."""
import json
import logging

import h3
from django.contrib.gis.db.models.functions import AsGeoJSON
from django.contrib.gis.geos import Polygon
from django.core.cache import cache
from django.db.models import Avg, Count, Max
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

    cache_key = f"risk_hexes:{bbox_str}:{ts_str}"
    cached = cache.get(cache_key)
    if cached is not None:
        return Response(cached)

    bbox_poly = Polygon.from_bbox((min_lng, min_lat, max_lng, max_lat))

    ts = _latest_ts()
    if ts_str:
        from django.utils.dateparse import parse_datetime
        parsed = parse_datetime(ts_str)
        if parsed:
            ts = parsed

    if ts is None:
        return Response({"type": "FeatureCollection", "features": []})

    snapshots = (
        RiskSnapshot.objects
        .filter(ts=ts, hex__centroid__within=bbox_poly)
        .select_related("hex")
        .annotate(geojson=AsGeoJSON("hex__geom"))
        .only("risk_level", "hazard_class", "confidence", "hex__h3_index")
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

    h3_index = h3.latlng_to_cell(lat, lng, 9)

    try:
        cell = HexCell.objects.get(h3_index=h3_index)
    except HexCell.DoesNotExist:
        return Response({"detail": "Location is outside the covered area."}, status=404)

    # Latest snapshot
    latest = (
        RiskSnapshot.objects
        .filter(hex=cell)
        .order_by("-ts")
        .first()
    )

    if not latest:
        return Response({
            "h3_index": h3_index,
            "risk_level": "LOW",
            "hazard_class": "LOW",
            "plain_text": "No forecast data yet — Low risk assumed.",
            "explanation": "Forecast data not yet available for this location.",
            "confidence": 0,
            "hourly": [],
        })

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
    cache_key = "risk_overview"
    cached = cache.get(cache_key)
    if cached is not None:
        return Response(cached)

    ts = _latest_ts()
    if ts is None:
        return Response({
            "forecast_rain_24h": 0,
            "max_rate_1h": 0,
            "confidence": 0,
            "summary": {"severe": 0, "high": 0, "moderate": 0, "low": 100},
            "hotspots": [],
        })

    snapshots = RiskSnapshot.objects.filter(ts=ts)
    total = snapshots.count()

    if total == 0:
        return Response({
            "forecast_rain_24h": 0, "max_rate_1h": 0, "confidence": 0,
            "summary": {"severe": 0, "high": 0, "moderate": 0, "low": 100},
            "hotspots": [],
        })

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
