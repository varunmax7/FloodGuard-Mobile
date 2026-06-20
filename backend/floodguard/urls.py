"""FloodGuard URL Configuration"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from floodguard.health import livez, readyz


urlpatterns = [
    # Django admin
    path("admin/", admin.site.urls),

    # Kubernetes / Railway probes
    path("api/v1/livez/",  livez,  name="livez"),
    path("api/v1/readyz/", readyz, name="readyz"),
    # Backwards-compatible alias kept for docker-compose healthcheck
    path("api/v1/health/", livez,  name="health-check"),

    # App routes (wired in later phases)
    path("api/v1/auth/", include("apps.accounts.urls")),
    path("api/v1/risk/", include("apps.risk.urls")),
    path("api/v1/radar/", include("apps.ingest.urls")),
    path("api/v1/reports/", include("apps.reports.urls")),
    path("api/v1/places/", include("apps.accounts.places_urls")),
    path("api/v1/alerts/", include("apps.alerts.urls")),
    path("api/v1/devices/", include("apps.accounts.devices_urls")),
    path("api/v1/admin/", include("apps.adminapi.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
