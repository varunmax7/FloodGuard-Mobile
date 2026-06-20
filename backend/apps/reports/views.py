"""reports/views.py — submit report + nearby reports."""
from datetime import timedelta

from django.contrib.gis.geos import Point
from django.contrib.gis.measure import Distance
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import FloodReport
from .serializers import FloodReportPublicSerializer


@api_view(["POST"])
def submit_report(request):
    """POST /api/v1/reports/ — Phase 8 implements the full multipart flow."""
    return Response({"detail": "Report submission implemented in Phase 8."}, status=501)


@api_view(["GET"])
@permission_classes([AllowAny])
def nearby_reports(request):
    """
    GET /api/v1/reports/nearby/?lat=&lng=&radius_m=1000&since_min=60

    Returns PENDING + VERIFIED reports within radius_m metres of the given
    point, observed within the last since_min minutes, newest first.
    """
    try:
        lat = float(request.query_params["lat"])
        lng = float(request.query_params["lng"])
    except (KeyError, ValueError, TypeError):
        return Response({"detail": "lat and lng are required float parameters."}, status=400)

    radius_m = int(request.query_params.get("radius_m", 1000))
    since_min = int(request.query_params.get("since_min", 60))

    radius_m = max(100, min(radius_m, 50_000))   # clamp 100m – 50km
    since_min = max(10, min(since_min, 10_080))   # clamp 10min – 7 days

    point = Point(lng, lat, srid=4326)
    cutoff = timezone.now() - timedelta(minutes=since_min)

    reports = (
        FloodReport.objects
        .filter(
            geom__distance_lte=(point, Distance(m=radius_m)),
            observed_at__gte=cutoff,
            status__in=["PENDING", "VERIFIED"],
        )
        .order_by("-observed_at")[:30]
    )

    serializer = FloodReportPublicSerializer(reports, many=True)
    return Response(serializer.data)
