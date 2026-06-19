"""reports/views.py — stub."""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@api_view(["POST"])
def submit_report(request):
    return Response({"detail": "Phase 4"}, status=501)


@api_view(["GET"])
@permission_classes([AllowAny])
def nearby_reports(request):
    return Response([], status=200)
