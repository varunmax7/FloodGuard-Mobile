"""adminapi/health.py — §2.4 System & Data Health endpoints."""
from datetime import timedelta

from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from .permissions import IsStaffAny

STALE_H = 2  # feeds older than 2 h are flagged red


@api_view(["GET"])
@permission_classes([IsStaffAny])
def feeds(request):
    """GET /api/v1/admin/health/feeds/ — ingest feed status with stale flags."""
    from apps.ingest.models import IngestLog
    now = timezone.now()
    result = []
    for log in IngestLog.objects.all():
        age_h = None
        stale = True
        if log.last_success:
            age_h = round((now - log.last_success).total_seconds() / 3600, 1)
            stale = age_h > STALE_H
        result.append({
            "feed":            log.feed,
            "last_success":    log.last_success.isoformat()    if log.last_success    else None,
            "last_attempted":  log.last_attempted.isoformat()  if log.last_attempted  else None,
            "last_error":      log.last_error or None,
            "records_written": log.records_written,
            "stale":           stale,
            "age_h":           age_h,
        })
    return Response(result)


@api_view(["GET"])
@permission_classes([IsStaffAny])
def stations(request):
    """GET /api/v1/admin/health/stations/ — AWS station uptime map."""
    from apps.geo.models import AwsStation, AwsObservation
    now = timezone.now()
    result = []
    for s in AwsStation.objects.all():
        last = AwsObservation.objects.filter(station=s).order_by("-ts").first()
        up   = bool(last and (now - last.ts).total_seconds() < STALE_H * 3600)
        result.append({
            "station_id": s.station_id,
            "name":       s.name,
            "lat":        s.geom.y,
            "lon":        s.geom.x,
            "last_obs":   last.ts.isoformat() if last else None,
            "up":         up,
        })
    return Response(result)


@api_view(["GET"])
@permission_classes([IsStaffAny])
def radar(request):
    """GET /api/v1/admin/health/radar/ — radar frame log + gap detection."""
    from apps.ingest.models import RadarFrame
    frames = list(RadarFrame.objects.order_by("-ts")[:48])

    gaps = []
    prev = None
    for f in reversed(frames):
        if prev:
            gap_min = (f.ts - prev).total_seconds() / 60
            if gap_min > 15:
                gaps.append({"from": prev.isoformat(), "to": f.ts.isoformat(), "gap_min": round(gap_min)})
        prev = f.ts

    return Response({
        "frames":        [{"ts": f.ts.isoformat(), "anomaly": f.anomaly, "dbz_max": f.dbz_max} for f in frames],
        "gaps":          gaps,
        "anomaly_count": sum(1 for f in frames if f.anomaly),
        "frame_count":   len(frames),
    })


@api_view(["GET"])
@permission_classes([IsStaffAny])
def api_errors(request):
    """GET /api/v1/admin/health/api-errors/ — API error rate panel (stub; wire to log aggregator in p13)."""
    return Response({
        "error_rate_1h":    0.0,
        "p95_latency_ms":   0,
        "total_requests_1h": 0,
        "note": "Wire to log aggregator in Phase 13",
    })
