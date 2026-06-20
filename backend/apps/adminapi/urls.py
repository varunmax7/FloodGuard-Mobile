"""adminapi/urls.py — all admin API routes (§2.1–2.8)."""
from django.urls import path
from . import views
from . import verify, validate, calibrate, health, moderation, analytics, export

urlpatterns = [
    # Auth
    path("auth/login/",  views.admin_login, name="admin-login"),
    path("auth/me/",     views.admin_me,    name="admin-me"),

    # §2.1 Forecast Verification
    path("verify/stations/",                             verify.station_list),
    path("verify/stations/<str:station_id>/timeseries/", verify.station_timeseries),
    path("verify/errors/",                               verify.error_metrics),
    path("verify/error-map/",                            verify.error_map),

    # §2.2 Report-vs-Risk Validation
    path("validate/reports-vs-risk/",  validate.reports_vs_risk),
    path("validate/confusion/",        validate.confusion_matrix),
    path("validate/hotspot-ranking/",  validate.hotspot_ranking),

    # §2.3 Calibration Console
    path("calibrate/weights/",  calibrate.weights),
    path("calibrate/preview/",  calibrate.preview),
    path("calibrate/backtest/", calibrate.backtest),

    # §2.4 System Health
    path("health/feeds/",      health.feeds),
    path("health/stations/",   health.stations),
    path("health/radar/",      health.radar),
    path("health/api-errors/", health.api_errors),

    # §2.5 Moderation Queue
    path("moderation/queue/",           moderation.queue),
    path("moderation/<str:pk>/action/", moderation.action),

    # §2.6 Analytics
    path("analytics/alerts/", analytics.alert_stats),
    path("analytics/usage/",  analytics.usage_stats),

    # §2.7 Export
    path("export/", export.export_query),

    # Audit logs (§2.8)
    path("audit/calibration/", views.audit_calibration),
    path("audit/moderation/",  views.audit_moderation),
]
