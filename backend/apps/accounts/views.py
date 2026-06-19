"""accounts/views.py — stub (full implementation Phase 5)."""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@api_view(["POST"])
@permission_classes([AllowAny])
def otp_request(request):
    """POST /api/v1/auth/otp/request — stub."""
    return Response({"detail": "Not implemented yet — Phase 5"}, status=501)


@api_view(["POST"])
@permission_classes([AllowAny])
def otp_verify(request):
    """POST /api/v1/auth/otp/verify — stub."""
    return Response({"detail": "Not implemented yet — Phase 5"}, status=501)
