"""adminapi/analytics.py — §2.6 Alert Analytics + usage stats."""
from datetime import timedelta

from django.db.models import Count
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from .permissions import IsStaffAny


@api_view(["GET"])
@permission_classes([IsStaffAny])
def alert_stats(request):
    """GET /api/v1/admin/analytics/alerts/ — delivery counts, by-level, top areas."""
    from apps.alerts.models import AlertDelivery, AlertEvent

    days = int(request.query_params.get("days", 30))
    since = timezone.now() - timedelta(days=days)

    by_status = dict(
        AlertDelivery.objects
        .filter(alert__created_at__gte=since)
        .values_list("status")
        .annotate(n=Count("id"))
        .values_list("status", "n")
    )

    by_level = dict(
        AlertEvent.objects
        .filter(created_at__gte=since)
        .values_list("risk_level")
        .annotate(n=Count("id"))
        .values_list("risk_level", "n")
    )

    top_areas = list(
        AlertEvent.objects
        .filter(created_at__gte=since, hex__isnull=False)
        .values("hex__h3_index", "hex__ward_name")
        .annotate(n=Count("id"))
        .order_by("-n")[:10]
        .values("hex__h3_index", "hex__ward_name", "n")
    )

    return Response({
        "by_status":  by_status,
        "by_level":   by_level,
        "top_areas":  top_areas,
        "period_days": days,
    })


@api_view(["GET"])
@permission_classes([IsStaffAny])
def usage_stats(request):
    """GET /api/v1/admin/analytics/usage/ — active users, report rate, dark hexes."""
    from apps.accounts.models import User
    from apps.geo.models import HexCell
    from apps.reports.models import FloodReport

    since = timezone.now() - timedelta(days=30)

    active_users = User.objects.filter(is_staff=False).exclude(fcm_token="").count()
    total_users  = User.objects.filter(is_staff=False).count()
    reports_30d  = FloodReport.objects.filter(created_at__gte=since).count()
    total_hexes  = HexCell.objects.count()
    active_hexes = (FloodReport.objects
                    .filter(created_at__gte=since, hex__isnull=False)
                    .values("hex").distinct().count())

    return Response({
        "active_users":  active_users,
        "total_users":   total_users,
        "reports_30d":   reports_30d,
        "total_hexes":   total_hexes,
        "active_hexes":  active_hexes,
        "dark_hexes":    max(0, total_hexes - active_hexes),
    })
