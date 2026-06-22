"""adminapi/moderation.py — §2.5 Moderation Queue with duplicate-detection hints."""
from datetime import timedelta

from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from .audit import log_moderation
from .permissions import IsOperatorOrAdmin


@api_view(["GET"])
@permission_classes([IsOperatorOrAdmin])
def queue(request):
    """GET /api/v1/admin/moderation/queue/ — pending reports with duplicate hints."""
    from apps.reports.models import FloodReport

    pending = (FloodReport.objects
               .filter(status="PENDING")
               .select_related("hex")
               .order_by("-created_at")[:50])

    result = []
    for r in pending:
        dupe_n = (FloodReport.objects
                  .filter(
                      hex=r.hex,
                      observed_at__gte=r.observed_at - timedelta(hours=1),
                      observed_at__lte=r.observed_at + timedelta(hours=1),
                      status="PENDING",
                  )
                  .exclude(pk=r.pk)
                  .count())

        result.append({
            "id":              str(r.id),
            "depth":           r.depth,
            "road":            r.road,
            "status":          r.status,
            "photo_url":       r.photo_url,
            "observed_at":     r.observed_at.isoformat(),
            "created_at":      r.created_at.isoformat(),
            "lat":             r.geom.y,
            "lon":             r.geom.x,
            "hex":             r.hex_id,
            "ward":            r.hex.ward_name if r.hex else None,
            "duplicate_hint":  dupe_n > 0,
            "duplicate_count": dupe_n,
        })
    return Response(result)


@api_view(["POST"])
@permission_classes([IsOperatorOrAdmin])
def action(request, pk):
    """POST /api/v1/admin/moderation/{pk}/action/ — body: {action: VERIFY|REJECT|SPAM}."""
    from apps.reports.models import FloodReport

    act = request.data.get("action", "").upper()
    if act not in ("VERIFY", "REJECT", "SPAM"):
        return Response({"detail": "action must be VERIFY, REJECT, or SPAM."}, status=400)

    try:
        report = FloodReport.objects.get(pk=pk)
    except FloodReport.DoesNotExist:
        return Response({"detail": "Not found."}, status=404)

    report.status = {"VERIFY": "VERIFIED", "REJECT": "REJECTED", "SPAM": "SPAM"}[act]
    report.save(update_fields=["status"])
    log_moderation(actor=request.user, report=report, action=act)

    if act == "VERIFY":
        from apps.alerts.tasks import dispatch_report_alert
        dispatch_report_alert.delay(str(report.id))

    return Response({"detail": f"Report {act}.", "status": report.status})
