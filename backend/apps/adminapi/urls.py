"""adminapi/urls.py — all admin API routes (§2.1–2.8)."""
from django.urls import path
from . import views

urlpatterns = [
    # Auth
    path("auth/login/",  views.admin_login, name="admin-login"),
    path("auth/me/",     views.admin_me,    name="admin-me"),

    # §2.1 Forecast Verification
    path("verify/stations/<str:station_id>/timeseries/", views.verify_station_timeseries),
    path("verify/errors/",     views.verify_errors),
    path("verify/error-map/",  views.verify_error_map),

    # §2.2 Report-vs-Risk Validation
    path("validate/reports-vs-risk/",   views.validate_reports_vs_risk),
    path("validate/confusion/",         views.validate_confusion),
    path("validate/hotspot-ranking/",   views.validate_hotspot_ranking),

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
