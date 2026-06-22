"""ingest/views.py — radar frames endpoint."""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import RadarFrame

# Standard WSR-88D / IMD Doppler intensity legend
INTENSITY_LEGEND = [
    {"dbz_min":  0, "dbz_max": 10, "color": "#00ffff", "label": "Trace"},
    {"dbz_min": 10, "dbz_max": 20, "color": "#00aaff", "label": "Light rain"},
    {"dbz_min": 20, "dbz_max": 30, "color": "#00cc00", "label": "Moderate rain"},
    {"dbz_min": 30, "dbz_max": 40, "color": "#ffff00", "label": "Heavy rain"},
    {"dbz_min": 40, "dbz_max": 50, "color": "#ff9900", "label": "Very heavy rain"},
    {"dbz_min": 50, "dbz_max": 60, "color": "#ff0000", "label": "Intense rain"},
    {"dbz_min": 60, "dbz_max": 75, "color": "#cc00cc", "label": "Extreme / hail"},
]


@api_view(["GET"])
@permission_classes([AllowAny])
def radar_frames(request):
    """
    GET /api/v1/radar/frames?since=<ISO datetime>

    Returns live radar frames from RainViewer.
    """
    import json
    import urllib.request
    from datetime import datetime
    from django.utils import timezone as django_timezone
    from datetime import timezone as dt_timezone
    
    # Check if DB has recent frames (within last hour)
    now = django_timezone.now()
    latest = RadarFrame.objects.order_by("-ts").first()
    
    # If DB is stale (older than 1 hour), fetch from RainViewer and update DB
    if not latest or (now - latest.ts).total_seconds() > 3600:
        try:
            url = 'https://api.rainviewer.com/public/weather-maps.json'
            with urllib.request.urlopen(url, timeout=5) as r:
                rv = json.loads(r.read().decode())
                
            host = rv['host']
            past_frames = rv['radar']['past']
            
            new_frames = []
            for frame in past_frames:
                ts = datetime.fromtimestamp(frame['time'], tz=dt_timezone.utc)
                tile_url = f"{host}{frame['path']}/256/{{z}}/{{x}}/{{y}}/4/1.png"
                new_frames.append(RadarFrame(
                    ts=ts,
                    tile_url_template=tile_url,
                    dbz_min=0.0,
                    dbz_max=75.0,
                    georef_ok=True,
                    anomaly=False,
                ))
            
            # Clear old and save new
            from django.db import transaction
            with transaction.atomic():
                RadarFrame.objects.all().delete()
                RadarFrame.objects.bulk_create(new_frames, ignore_conflicts=True)
                
        except Exception as e:
            import logging
            logger = logging.getLogger("floodguard.ingest")
            logger.error(f"Failed to fetch RainViewer data: {e}")

    # Return from DB (either just updated or still fresh)
    qs = RadarFrame.objects.filter(georef_ok=True).order_by("-ts")

    since_str = request.query_params.get("since")
    if since_str:
        from django.utils.dateparse import parse_datetime
        since = parse_datetime(since_str)
        if since:
            qs = qs.filter(ts__gte=since)

    frames = [
        {
            "ts": frame.ts.isoformat(),
            "tile_url_template": frame.tile_url_template,
            "dbz_min": frame.dbz_min,
            "dbz_max": frame.dbz_max,
            "anomaly": frame.anomaly,
            "intensity_legend": INTENSITY_LEGEND,
        }
        for frame in qs[:48]   # max 48 frames (~8h at 10-min intervals)
    ]
    return Response(frames)
