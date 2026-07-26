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

    # Optional: how many people are with the reporter (default 1 = alone).
    try:
        party_size = int(data.get("party_size", 1) or 1)
    except (ValueError, TypeError):
        party_size = 1
    party_size = max(1, min(party_size, 99))

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
        from django.conf import settings as _settings
        h3_index = h3.latlng_to_cell(lat, lng, _settings.H3_RESOLUTION)
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
        party_size=party_size,
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


# Depth → intensity weight used by the client-side heatmap layer.
# Higher water levels contribute more to the heat ramp.
_DEPTH_WEIGHT = {"ANKLE": 1.0, "KNEE": 2.0, "WAIST": 3.0, "VEHICLE": 4.0}


@api_view(["GET"])
@permission_classes([AllowAny])
def reports_heatmap(request):
    """
    GET /api/v1/reports/heatmap/?since_hours=24&bbox=minLng,minLat,maxLng,maxLat

    Returns a GeoJSON FeatureCollection of recent PENDING/VERIFIED reports
    for rendering as a heatmap overlay on the radar map. Each feature carries
    a `weight` (1–4) derived from the reported depth so that deeper reports
    burn brighter on the heatmap.
    """
    try:
        since_hours = int(request.query_params.get("since_hours", 24))
    except (ValueError, TypeError):
        since_hours = 24
    since_hours = max(1, min(since_hours, 168))  # clamp 1h – 7 days

    qs = FloodReport.objects.filter(
        observed_at__gte=timezone.now() - timedelta(hours=since_hours),
        status__in=["PENDING", "VERIFIED"],
    )

    bbox = request.query_params.get("bbox")
    if bbox:
        try:
            min_lng, min_lat, max_lng, max_lat = (float(x) for x in bbox.split(","))
            from django.contrib.gis.geos import Polygon
            qs = qs.filter(
                geom__within=Polygon.from_bbox((min_lng, min_lat, max_lng, max_lat))
            )
        except (ValueError, TypeError):
            pass  # ignore malformed bbox and return full set

    features = []
    for r in qs.only("id", "geom", "depth", "status", "observed_at")[:500]:
        if r.geom is None:
            continue
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [r.geom.x, r.geom.y]},
            "properties": {
                "id": str(r.id),
                "depth": r.depth,
                "status": r.status,
                "weight": _DEPTH_WEIGHT.get(r.depth, 1.0),
                "observed_at": r.observed_at.isoformat(),
            },
        })

    return Response({"type": "FeatureCollection", "features": features})
