"""adminapi/validate.py — §2.2 Report-vs-Risk Validation endpoints."""
from datetime import timedelta

from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from .permissions import IsStaffAny

RISK_LEVELS = ["LOW", "MODERATE", "HIGH", "SEVERE"]
RISK_RANK   = {"LOW": 0, "MODERATE": 1, "HIGH": 2, "SEVERE": 3}


def _range(request, default_days=30):
    now = timezone.now()
    t_from = parse_datetime(request.query_params.get("from", "") or "") or (now - timedelta(days=default_days))
    t_to   = parse_datetime(request.query_params.get("to",   "") or "") or now
    return t_from, t_to


# ── §2.2a: reports overlaid on active risk ────────────────────────────────────

@api_view(["GET"])
@permission_classes([IsStaffAny])
def reports_vs_risk(request):
    """
    GET /api/v1/admin/validate/reports-vs-risk/?from=&to=
    Returns verified/rejected reports with the risk level active at report time.
    """
    from apps.reports.models import FloodReport
    from apps.risk.models import RiskSnapshot

    t_from, t_to = _range(request)
    reports = (
        FloodReport.objects
        .filter(status__in=("VERIFIED", "REJECTED"),
                observed_at__gte=t_from, observed_at__lte=t_to,
                hex__isnull=False)
        .select_related("hex")
        .order_by("-observed_at")[:200]
    )

    rows = []
    for r in reports:
        snap = (
            RiskSnapshot.objects
            .filter(hex_id=r.hex_id, ts__lte=r.observed_at)
            .order_by("-ts")
            .first()
        )
        rows.append({
            "report_id":    str(r.id),
            "status":       r.status,
            "depth":        r.depth,
            "observed_at":  r.observed_at.isoformat(),
            "hex":          r.hex_id,
            "risk_at_time": snap.risk_level if snap else None,
            "lat":          r.geom.y,
            "lon":          r.geom.x,
        })

    return Response(rows)


# ── §2.2b: confusion matrix ───────────────────────────────────────────────────

@api_view(["GET"])
@permission_classes([IsStaffAny])
def confusion_matrix(request):
    """
    GET /api/v1/admin/validate/confusion/?from=&to=
    Predicted risk level × actual outcome (VERIFIED=flooded, REJECTED=not flooded).
    """
    from apps.reports.models import FloodReport
    from apps.risk.models import RiskSnapshot

    t_from, t_to = _range(request)
    reports = (
        FloodReport.objects
        .filter(status__in=("VERIFIED", "REJECTED"),
                observed_at__gte=t_from, observed_at__lte=t_to,
                hex__isnull=False)
        .select_related("hex")
    )

    matrix = {lvl: {"flooded": 0, "not_flooded": 0} for lvl in RISK_LEVELS}
    total  = 0

    for r in reports:
        snap = (
            RiskSnapshot.objects
            .filter(hex_id=r.hex_id, ts__lte=r.observed_at)
            .order_by("-ts")
            .first()
        )
        if not snap:
            continue
        col = "flooded" if r.status == "VERIFIED" else "not_flooded"
        matrix[snap.risk_level][col] += 1
        total += 1

    fn = sum(matrix[l]["not_flooded"] for l in ("HIGH", "SEVERE"))   # missed floods
    fp = sum(matrix[l]["flooded"]     for l in ("LOW", "MODERATE"))  # false alarms

    return Response({
        "matrix":          matrix,
        "total":           total,
        "false_negatives": fn,
        "false_positives": fp,
        "from": t_from.isoformat(),
        "to":   t_to.isoformat(),
    })


# ── §2.2c: hotspot accuracy ranking ──────────────────────────────────────────

@api_view(["GET"])
@permission_classes([IsStaffAny])
def hotspot_ranking(request):
    """
    GET /api/v1/admin/validate/hotspot-ranking
    Areas ranked by model-vs-report agreement (last 30 days).
    """
    from apps.reports.models import FloodReport
    from apps.risk.models import RiskSnapshot

    since = timezone.now() - timedelta(days=30)
    reports = (
        FloodReport.objects
        .filter(status__in=("VERIFIED", "REJECTED"), observed_at__gte=since, hex__isnull=False)
        .select_related("hex")
    )

    stats: dict = {}
    for r in reports:
        h3 = r.hex_id
        if h3 not in stats:
            stats[h3] = {"agree": 0, "disagree": 0, "total": 0, "ward_name": r.hex.ward_name}
        snap = (
            RiskSnapshot.objects
            .filter(hex_id=h3, ts__lte=r.observed_at)
            .order_by("-ts")
            .first()
        )
        if not snap:
            continue
        rank    = RISK_RANK.get(snap.risk_level, 0)
        flooded = r.status == "VERIFIED"
        agree   = (flooded and rank >= 2) or (not flooded and rank < 2)
        stats[h3]["agree" if agree else "disagree"] += 1
        stats[h3]["total"] += 1

    ranking = sorted(
        [
            {
                "h3_index":  h3,
                "ward_name": v["ward_name"],
                "agree":     v["agree"],
                "disagree":  v["disagree"],
                "total":     v["total"],
                "accuracy":  round(v["agree"] / v["total"], 3) if v["total"] else 0,
            }
            for h3, v in stats.items()
            if v["total"] > 0
        ],
        key=lambda x: x["accuracy"],
        reverse=True,
    )

    return Response(ranking[:50])
