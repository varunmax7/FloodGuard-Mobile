"""risk/views.py — stub."""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@api_view(["GET"])
@permission_classes([AllowAny])
def risk_hexes(request):
    return Response({"type": "FeatureCollection", "features": []}, status=200)


@api_view(["GET"])
def risk_location(request):
    return Response({"detail": "Phase 3"}, status=501)


@api_view(["GET"])
@permission_classes([AllowAny])
def risk_overview(request):
    return Response({"detail": "Phase 3"}, status=501)
