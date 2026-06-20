"""adminapi/urls.py — all admin API routes (§2.1–2.8)."""
from django.urls import path
from . import views
from . import verify, validate

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
    path("validate/reports-vs-risk/",   validate.reports_vs_risk),
    path("validate/confusion/",         validate.confusion_matrix),
    path("validate/hotspot-ranking/",   validate.hotspot_ranking),

    # §2.3 Calibration Console
    path("calibrate/weights/",          views.calibrate_weights),
    path("calibrate/backtest/",         views.calibrate_backtest),

    # §2.4 System Health
    path("health/feeds/",    views.health_feeds),
    path("health/stations/", views.health_stations),

    # §2.5 Moderation Queue
    path("moderation/queue/",              views.moderation_queue),
    path("moderation/<str:pk>/action/",    views.moderation_action),

    # §2.6 Analytics
    path("analytics/alerts/", views.analytics_alerts),

    # §2.7 Export
    path("export/", views.export_data),

    # Audit logs
    path("audit/calibration/", views.audit_calibration),
    path("audit/moderation/",  views.audit_moderation),
]
