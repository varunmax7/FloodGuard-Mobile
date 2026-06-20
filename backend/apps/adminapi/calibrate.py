"""adminapi/calibrate.py — §2.3 Calibration Console endpoints."""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from .audit import log_calibration
from .permissions import CalibrationPermission, IsStaffAny

LAYER_KEYS = ("twi", "depression_depth", "hand", "dist_to_water", "slope", "imperviousness")

DEFAULTS = {
    "twi": 0.25, "depression_depth": 0.20, "hand": 0.20,
    "dist_to_water": 0.15, "slope": 0.10, "imperviousness": 0.10,
    "threshold_low": 0.25, "threshold_moderate": 0.50, "threshold_high": 0.75,
    "hazard_low": 5.0, "hazard_moderate": 15.0, "hazard_high": 30.0,
}


def _current():
    from apps.risk.models import FsiWeights
    w = FsiWeights.objects.first()
    if not w:
        return dict(DEFAULTS)
    return {
        "twi": w.twi, "depression_depth": w.depression_depth,
        "hand": w.hand, "dist_to_water": w.dist_to_water,
        "slope": w.slope, "imperviousness": w.imperviousness,
        "threshold_low": w.threshold_low, "threshold_moderate": w.threshold_moderate,
        "threshold_high": w.threshold_high,
        "hazard_low": w.hazard_low, "hazard_moderate": w.hazard_moderate,
        "hazard_high": w.hazard_high,
        "updated_at": w.updated_at.isoformat(), "updated_by": w.updated_by,
    }


def _risk_from_score(score, w):
    if score >= w.get("threshold_high", 0.75):
        return "HIGH"
    if score >= w.get("threshold_moderate", 0.50):
        return "MODERATE"
    return "LOW"


def _fsi(inputs, w):
    return sum(float(inputs.get(k, 0)) * float(w.get(k, 0)) for k in LAYER_KEYS)


# ── GET/PUT weights ───────────────────────────────────────────────────────────

@api_view(["GET", "PUT"])
@permission_classes([CalibrationPermission])
def weights(request):
    """GET — any staff; PUT — ADMIN only, saves new FsiWeights row + CalibrationLog."""
    if request.method == "GET":
        return Response(_current())

    from apps.risk.models import FsiWeights
    before = _current()
    d = request.data

    w = FsiWeights(
        twi=d.get("twi",               DEFAULTS["twi"]),
        depression_depth=d.get("depression_depth", DEFAULTS["depression_depth"]),
        hand=d.get("hand",             DEFAULTS["hand"]),
        dist_to_water=d.get("dist_to_water",   DEFAULTS["dist_to_water"]),
        slope=d.get("slope",           DEFAULTS["slope"]),
        imperviousness=d.get("imperviousness",  DEFAULTS["imperviousness"]),
        threshold_low=d.get("threshold_low",    DEFAULTS["threshold_low"]),
        threshold_moderate=d.get("threshold_moderate", DEFAULTS["threshold_moderate"]),
        threshold_high=d.get("threshold_high",  DEFAULTS["threshold_high"]),
        hazard_low=d.get("hazard_low",     DEFAULTS["hazard_low"]),
        hazard_moderate=d.get("hazard_moderate", DEFAULTS["hazard_moderate"]),
        hazard_high=d.get("hazard_high",   DEFAULTS["hazard_high"]),
        updated_by=request.user.phone,
    )
    w.save()
    after = _current()
    log_calibration(actor=request.user.phone, change_type="fsi_weights", before=before, after=after)
    return Response(after)


# ── Preview ───────────────────────────────────────────────────────────────────

@api_view(["POST"])
@permission_classes([IsStaffAny])
def preview(request):
    """
    POST /api/v1/admin/calibrate/preview/
    Body: {weights: {...}, date: "YYYY-MM-DD"}
    Returns hex-level diff between current and proposed risk levels.
    """
    from apps.geo.models import HexCell
    from apps.risk.models import RiskSnapshot
    from datetime import timedelta
    from django.utils import timezone

    proposed = request.data.get("weights", DEFAULTS)
    date_str = request.data.get("date")

    if date_str:
        from django.utils.dateparse import parse_date
        d = parse_date(date_str)
        if d:
            ts_from = timezone.datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
            ts_to   = ts_from + timedelta(days=1)
        else:
            ts_to   = timezone.now()
            ts_from = ts_to - timedelta(hours=24)
    else:
        ts_to   = timezone.now()
        ts_from = ts_to - timedelta(hours=24)

    results = []
    for hex_ in HexCell.objects.filter(fsi_score__gt=0)[:100]:
        new_score = _fsi(hex_.fsi_inputs or {}, proposed)
        new_risk  = _risk_from_score(new_score, proposed)
        snap = RiskSnapshot.objects.filter(hex=hex_, ts__gte=ts_from, ts__lt=ts_to).order_by("-ts").first()
        current_risk = snap.risk_level if snap else None
        results.append({
            "h3_index":    hex_.h3_index,
            "ward_name":   hex_.ward_name,
            "current_fsi": round(hex_.fsi_score, 3),
            "new_fsi":     round(new_score, 3),
            "current_risk": current_risk,
            "new_risk":    new_risk,
            "changed":     current_risk != new_risk,
        })

    changed = [r for r in results if r["changed"]]
    return Response({
        "total_hexes": len(results),
        "changed":     len(changed),
        "preview":     results[:50],
    })


# ── Backtest ──────────────────────────────────────────────────────────────────

@api_view(["POST"])
@permission_classes([CalibrationPermission])
def backtest(request):
    """
    POST /api/v1/admin/calibrate/backtest/
    Body: {weights: {...}}
    Evaluates proposed weights against all VERIFIED flood reports.
    """
    from apps.reports.models import FloodReport

    proposed = request.data.get("weights", DEFAULTS)
    reports  = (FloodReport.objects
                .filter(status="VERIFIED", hex__isnull=False)
                .select_related("hex")[:200])

    agree = disagree = 0
    results = []
    for r in reports:
        new_score = _fsi(r.hex.fsi_inputs or {}, proposed)
        new_risk  = _risk_from_score(new_score, proposed)
        correct   = new_risk in ("HIGH", "SEVERE")
        if correct:
            agree += 1
        else:
            disagree += 1
        results.append({
            "report_id": str(r.id),
            "hex":       r.hex_id,
            "ward_name": r.hex.ward_name,
            "new_fsi":   round(new_score, 3),
            "new_risk":  new_risk,
            "correct":   correct,
        })

    total = len(results)
    return Response({
        "total":    total,
        "correct":  agree,
        "incorrect": disagree,
        "accuracy": round(agree / total, 3) if total else 0,
        "results":  results[:50],
    })
