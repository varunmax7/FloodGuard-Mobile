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
@permission_classes([AllowAny])
def submit_report(request):
    """
    POST /api/v1/reports/  (multipart/form-data)

    Required fields: lat, lng, depth, road, client_uuid, observed_at
    Optional: photo (image file)
    """
    import uuid as _uuid
    from django.utils.dateparse import parse_datetime
    from django.core.files.storage import default_storage
    from django.core.files.base import ContentFile

    data = request.data

    # ── Validate required fields ─────────────────────────────────────────
    try:
        lat = float(data.get("lat", ""))
        lng = float(data.get("lng", ""))
    except (ValueError, TypeError):
        return Response({"detail": "lat and lng are required floats."}, status=400)

    depth = data.get("depth", "")
    road = data.get("road", "")
    client_uuid_str = data.get("client_uuid", "")
    observed_at_str = data.get("observed_at", "")

    if depth not in ("ANKLE", "KNEE", "WAIST", "VEHICLE"):
        return Response({"detail": "depth must be ANKLE, KNEE, WAIST, or VEHICLE."}, status=400)
    if road not in ("PASSABLE", "DIFFICULT", "BLOCKED"):
        return Response({"detail": "road must be PASSABLE, DIFFICULT, or BLOCKED."}, status=400)
    if not client_uuid_str:
        return Response({"detail": "client_uuid is required."}, status=400)

    try:
        client_uuid = _uuid.UUID(client_uuid_str)
    except ValueError:
        return Response({"detail": "client_uuid must be a valid UUID."}, status=400)

    observed_at = parse_datetime(observed_at_str)
    if not observed_at:
        observed_at = timezone.now()

    # ── Idempotency — reject duplicate client_uuid ───────────────────────
    if FloodReport.objects.filter(client_uuid=client_uuid).exists():
        existing = FloodReport.objects.get(client_uuid=client_uuid)
        return Response({
            "detail": "Report already submitted.",
            "id": str(existing.id),
        }, status=200)

    # ── Handle photo upload ──────────────────────────────────────────────
    photo_url = ""
    photo_file = request.FILES.get("photo")
    if photo_file:
        ext = photo_file.name.rsplit(".", 1)[-1] if "." in photo_file.name else "jpg"
        filename = f"reports/{client_uuid}.{ext}"
        saved_path = default_storage.save(filename, ContentFile(photo_file.read()))
        # Build full URL for the photo
        photo_url = request.build_absolute_uri(f"/media/{saved_path}")

    # ── Create PostGIS point ─────────────────────────────────────────────
    geom = Point(lng, lat, srid=4326)

    # ── Optionally link to H3 hex cell ───────────────────────────────────
    hex_cell = None
    try:
        import h3
        h3_index = h3.latlng_to_cell(lat, lng, 9)
        from apps.geo.models import HexCell
        hex_cell = HexCell.objects.filter(pk=h3_index).first()
    except Exception:
        pass  # h3 not installed or hex not found — fine

    # ── Create report ────────────────────────────────────────────────────
    report = FloodReport.objects.create(
        user=request.user if request.user.is_authenticated else None,
        geom=geom,
        hex=hex_cell,
        photo_url=photo_url,
        depth=depth,
        road=road,
        status="PENDING",
        observed_at=observed_at,
        client_uuid=client_uuid,
    )

    return Response({
        "detail": "Report submitted successfully.",
        "id": str(report.id),
        "status": report.status,
    }, status=201)


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
