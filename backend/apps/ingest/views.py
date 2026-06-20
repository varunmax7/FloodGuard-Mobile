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

    Returns radar frames ordered by ts desc.
    Excludes frames where georef_ok=False.
    Each frame includes a fixed intensity_legend.
    """
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
