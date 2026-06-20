"""adminapi/export.py — §2.7 Historical Query & Export (CSV + GeoJSON)."""
import json
from datetime import timedelta

from django.http import HttpResponse, StreamingHttpResponse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.decorators import api_view, permission_classes

from .permissions import IsStaffAny


def _range(request, default_days=7):
    now    = timezone.now()
    t_from = parse_datetime(request.query_params.get("from", "") or "") or (now - timedelta(days=default_days))
    t_to   = parse_datetime(request.query_params.get("to",   "") or "") or now
    return t_from, t_to


@api_view(["GET"])
@permission_classes([IsStaffAny])
def export_query(request):
    """
    GET /api/v1/admin/export/?from=&to=&format=csv|geojson&type=reports|risk
    Streams the requested dataset as CSV or GeoJSON attachment.
    """
    t_from, t_to = _range(request)
    fmt   = request.query_params.get("fmt",  "csv").lower()
    dtype = request.query_params.get("type", "reports").lower()

    if dtype == "risk":
        return _risk(t_from, t_to, fmt)
    return _reports(t_from, t_to, fmt)


# ── Reports ───────────────────────────────────────────────────────────────────

def _reports(t_from, t_to, fmt):
    from apps.reports.models import FloodReport
    qs = (FloodReport.objects
          .filter(observed_at__gte=t_from, observed_at__lte=t_to)
          .select_related("hex")
          .order_by("-observed_at"))

    if fmt == "geojson":
        features = [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [r.geom.x, r.geom.y]},
                "properties": {
                    "id": str(r.id), "status": r.status,
                    "depth": r.depth, "road": r.road,
                    "observed_at": r.observed_at.isoformat(),
                    "hex": r.hex_id,
                    "ward": r.hex.ward_name if r.hex else None,
                },
            }
            for r in qs
        ]
        resp = HttpResponse(
            json.dumps({"type": "FeatureCollection", "features": features}, indent=2),
            content_type="application/geo+json",
        )
        resp["Content-Disposition"] = 'attachment; filename="reports.geojson"'
        return resp

    def rows():
        yield "id,status,depth,road,lat,lon,observed_at,hex,ward\r\n"
        for r in qs:
            ward = r.hex.ward_name if r.hex else ""
            yield f'{r.id},{r.status},{r.depth},{r.road},{r.geom.y},{r.geom.x},{r.observed_at.isoformat()},{r.hex_id or ""},{ward}\r\n'

    resp = StreamingHttpResponse(rows(), content_type="text/csv")
    resp["Content-Disposition"] = 'attachment; filename="reports.csv"'
    return resp


# ── Risk snapshots ────────────────────────────────────────────────────────────

def _risk(t_from, t_to, fmt):
    from apps.risk.models import RiskSnapshot
    qs = (RiskSnapshot.objects
          .filter(ts__gte=t_from, ts__lte=t_to)
          .select_related("hex")
          .order_by("-ts"))

    if fmt == "geojson":
        features = [
            {
                "type": "Feature",
                "geometry": (
                    {"type": "Point", "coordinates": [s.hex.centroid.x, s.hex.centroid.y]}
                    if s.hex.centroid else None
                ),
                "properties": {
                    "h3_index": s.hex_id, "risk_level": s.risk_level,
                    "hazard_class": s.hazard_class, "ts": s.ts.isoformat(),
                    "rain_1h": s.rain_1h, "confidence": s.confidence,
                },
            }
            for s in qs if s.hex.centroid
        ]
        resp = HttpResponse(
            json.dumps({"type": "FeatureCollection", "features": features}, indent=2),
            content_type="application/geo+json",
        )
        resp["Content-Disposition"] = 'attachment; filename="risk_snapshots.geojson"'
        return resp

    def rows():
        yield "h3_index,risk_level,hazard_class,ts,rain_1h,confidence\r\n"
        for s in qs:
            yield f"{s.hex_id},{s.risk_level},{s.hazard_class},{s.ts.isoformat()},{s.rain_1h or ''},{s.confidence}\r\n"

    resp = StreamingHttpResponse(rows(), content_type="text/csv")
    resp["Content-Disposition"] = 'attachment; filename="risk_snapshots.csv"'
    return resp
