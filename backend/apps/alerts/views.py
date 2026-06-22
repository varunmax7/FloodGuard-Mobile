"""alerts/views.py — GET /api/v1/alerts/?scope=active|history"""
from datetime import timedelta

import h3 as h3lib
from django.db.models import Q
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.models import SavedPlace
from .models import AlertEvent
from .serializers import AlertEventSerializer


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def alerts_list(request):
    """
    GET /api/v1/alerts/?scope=active|history

    Returns AlertEvents for the user's saved places.
    - RISK alerts: exact hex match.
    - REPORT alerts: extended to k=2 ring (~500 m) so nearby verified
      reports also surface even when the exact hex differs.
    active  → window_end within the last 24 h (default)
    history → all alerts, up to 50 most recent
    """
    scope = request.query_params.get("scope", "active")

    user_hex_ids = list(
        SavedPlace.objects
        .filter(user=request.user, hex__isnull=False)
        .values_list("hex_id", flat=True)
    )

    # Expand hex set for report-type alerts
    nearby_hex_ids: set[str] = set()
    for hid in user_hex_ids:
        nearby_hex_ids.update(h3lib.grid_disk(hid, 2))

    qs = (
        AlertEvent.objects
        .filter(
            Q(hex_id__in=user_hex_ids) |
            Q(source="REPORT", hex_id__in=nearby_hex_ids)
        )
        .select_related("hex", "report")
    )

    if scope == "active":
        cutoff = timezone.now() - timedelta(hours=24)
        qs = qs.filter(window_end__gte=cutoff)

    qs = qs.order_by("-window_start")[:50]
    return Response(AlertEventSerializer(qs, many=True).data)
