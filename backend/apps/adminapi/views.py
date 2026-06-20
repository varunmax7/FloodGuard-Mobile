"""adminapi/views.py — Admin JWT login + section stubs (§2.1–2.8)."""
import logging

from django.contrib.auth import authenticate
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from .audit import log_calibration, log_moderation
from .permissions import CalibrationPermission, IsOperatorOrAdmin, IsStaffAny

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
    phone    = request.data.get("phone", "").strip()
    password = request.data.get("password", "")

    if not phone or not password:
        return Response({"detail": "phone and password required."}, status=400)

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


# ── §2.1 Forecast Verification (full impl Phase 11) ──────────────────────────

@api_view(["GET"])
@permission_classes([IsStaffAny])
def verify_station_timeseries(request, station_id):
    return Response({"detail": "Phase 11", "station_id": station_id}, status=501)


@api_view(["GET"])
@permission_classes([IsStaffAny])
def verify_errors(request):
    return Response({"detail": "Phase 11"}, status=501)


@api_view(["GET"])
@permission_classes([IsStaffAny])
def verify_error_map(request):
    return Response({"detail": "Phase 11"}, status=501)


# ── §2.2 Report-vs-Risk Validation (full impl Phase 11) ──────────────────────

@api_view(["GET"])
@permission_classes([IsStaffAny])
def validate_reports_vs_risk(request):
    return Response({"detail": "Phase 11"}, status=501)


@api_view(["GET"])
@permission_classes([IsStaffAny])
def validate_confusion(request):
    return Response({"detail": "Phase 11"}, status=501)


@api_view(["GET"])
@permission_classes([IsStaffAny])
def validate_hotspot_ranking(request):
    return Response({"detail": "Phase 11"}, status=501)


# ── §2.3 Calibration Console (full impl Phase 12) ────────────────────────────

@api_view(["GET", "PUT"])
@permission_classes([CalibrationPermission])
def calibrate_weights(request):
    """GET — any staff; PUT — ADMIN only, writes CalibrationLog."""
    if request.method == "GET":
        return Response({"detail": "Phase 12 — FSI weights placeholder"}, status=200)

    # PUT — record audit log
    log_calibration(
        actor=request.user.phone,
        change_type="weights",
        before={"note": "previous weights"},
        after=request.data,
    )
    return Response({"detail": "Phase 12 — weights updated", "data": request.data})


@api_view(["POST"])
@permission_classes([CalibrationPermission])
def calibrate_backtest(request):
    return Response({"detail": "Phase 12"}, status=501)


# ── §2.4 System Health (full impl Phase 12) ───────────────────────────────────

@api_view(["GET"])
@permission_classes([IsStaffAny])
def health_feeds(request):
    """Returns last-ingest timestamps per feed."""
    from apps.ingest.models import IngestLog
    logs = IngestLog.objects.order_by("source", "-ts").distinct("source")
    data = [{"source": l.source, "last_ts": l.ts, "ok": l.ok} for l in logs]
    return Response(data)


@api_view(["GET"])
@permission_classes([IsStaffAny])
def health_stations(request):
    return Response({"detail": "Phase 12"}, status=501)


# ── §2.5 Moderation Queue (full impl Phase 12) ────────────────────────────────

@api_view(["GET"])
@permission_classes([IsOperatorOrAdmin])
def moderation_queue(request):
    from apps.reports.models import FloodReport
    from apps.reports.serializers import FloodReportSerializer
    qs = FloodReport.objects.filter(status="PENDING").order_by("-created_at")[:50]
    return Response(FloodReportSerializer(qs, many=True).data)


@api_view(["POST"])
@permission_classes([IsOperatorOrAdmin])
def moderation_action(request, pk):
    """POST /api/v1/admin/moderation/{pk}/action/ body: {action: VERIFY|REJECT|SPAM}"""
    from apps.reports.models import FloodReport
    action = request.data.get("action", "").upper()
    if action not in ("VERIFY", "REJECT", "SPAM"):
        return Response({"detail": "action must be VERIFY, REJECT, or SPAM."}, status=400)

    try:
        report = FloodReport.objects.get(pk=pk)
    except FloodReport.DoesNotExist:
        return Response({"detail": "Not found."}, status=404)

    status_map = {"VERIFY": "VERIFIED", "REJECT": "REJECTED", "SPAM": "SPAM"}
    report.status = status_map[action]
    report.save(update_fields=["status"])

    log_moderation(actor=request.user, report=report, action=action)
    return Response({"detail": f"Report {action}D.", "status": report.status})


# ── §2.6 Analytics (full impl Phase 12) ──────────────────────────────────────

@api_view(["GET"])
@permission_classes([IsStaffAny])
def analytics_alerts(request):
    return Response({"detail": "Phase 12"}, status=501)


# ── §2.7 Historical Export (full impl Phase 12) ───────────────────────────────

@api_view(["GET"])
@permission_classes([IsStaffAny])
def export_data(request):
    return Response({"detail": "Phase 12"}, status=501)


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
    logs = ModerationLog.objects.select_related("actor", "report").order_by("-ts")[:50]
    return Response([
        {"actor": l.actor.phone if l.actor else None, "action": l.action,
         "report_id": str(l.report.id) if l.report else None, "ts": l.ts}
        for l in logs
    ])
