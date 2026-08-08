"""adminapi/views.py — Admin JWT login + section stubs (§2.1–2.8)."""
import logging

from django.contrib.auth import authenticate
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from .permissions import IsStaffAny

logger = logging.getLogger("floodguard.admin")

# ── Auth ──────────────────────────────────────────────────────────────────────

@api_view(["POST"])
@permission_classes([AllowAny])
def admin_login(request):
    """
    POST /api/v1/admin/auth/login/
    Body: {phone, password}
    Returns: {access, refresh, user: {phone, role}}
    """
    from apps.accounts.serializers import _normalize_phone
    phone    = request.data.get("phone", "").strip()
    password = request.data.get("password", "")

    if not phone or not password:
        return Response({"detail": "phone and password required."}, status=400)

    phone = _normalize_phone(phone)
    user = authenticate(request, phone=phone, password=password)
    if not user:
        return Response({"detail": "Invalid credentials."}, status=status.HTTP_401_UNAUTHORIZED)
    if not user.is_staff:
        return Response({"detail": "Admin access required."}, status=status.HTTP_403_FORBIDDEN)

    refresh = RefreshToken.for_user(user)
    # Embed role in access token custom claim
    refresh.access_token["role"] = user.role
    refresh.access_token["phone"] = user.phone

    return Response({
        "access":  str(refresh.access_token),
        "refresh": str(refresh),
        "user": {"id": str(user.id), "phone": user.phone, "role": user.role},
    })


@api_view(["GET"])
@permission_classes([IsStaffAny])
def admin_me(request):
    """GET /api/v1/admin/auth/me/ — current admin user info."""
    return Response({
        "id":    str(request.user.id),
        "phone": request.user.phone,
        "role":  request.user.role,
    })


# ── Audit log read endpoints ──────────────────────────────────────────────────

@api_view(["GET"])
@permission_classes([IsStaffAny])
def audit_calibration(request):
    from apps.risk.models import CalibrationLog
    logs = CalibrationLog.objects.order_by("-ts")[:50]
    return Response([
        {"actor": l.actor, "change_type": l.change_type, "ts": l.ts}
        for l in logs
    ])


@api_view(["GET"])
@permission_classes([IsStaffAny])
def audit_moderation(request):
    from apps.reports.models import ModerationLog
    from apps.reports.photo_urls import resolve_photo_url
    logs = ModerationLog.objects.select_related("actor", "report", "report__hex").order_by("-ts")[:50]
    result = []
    for l in logs:
        r = l.report
        result.append({
            "actor": l.actor.phone if l.actor else None,
            "action": l.action,
            "ts": l.ts,
            "report_id": str(r.id) if r else None,
            "photo_url": resolve_photo_url(r.photo_url) if r else None,
            "depth": r.depth if r else None,
            "road": r.road if r else None,
            "status": r.status if r else None,
            "party_size": r.party_size if r else None,
            "description": r.description if r else None,
            "observed_at": r.observed_at.isoformat() if r else None,
            "created_at": r.created_at.isoformat() if r else None,
            "lat": r.geom.y if r and r.geom else None,
            "lon": r.geom.x if r and r.geom else None,
            "ward": r.hex.ward_name if r and r.hex else None,
        })
    return Response(result)
