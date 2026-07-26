"""FloodGuard URL Configuration"""
from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from floodguard.health import livez, readyz
from floodguard import spa


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

    # Lightweight fallback report page — fast to load on flaky networks.
    path("quick/", TemplateView.as_view(template_name="report.html"), name="quick-report"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# ── Flutter web SPA ──────────────────────────────────────────────────────────
# Order matters: hashed/asset paths first, then top-level Flutter files, then
# the catch-all fallback that returns index.html for client-side routing.
urlpatterns += [
    re_path(r"^(?P<path>(?:assets|canvaskit|icons)/.*)$", spa.spa_static),
    re_path(
        r"^(?P<filename>main\.dart\.js|flutter\.js|flutter_bootstrap\.js|"
        r"flutter_service_worker\.js|favicon\.png|manifest\.json|version\.json)$",
        spa.spa_root_file,
    ),
    # SPA fallback — must be last, and must NOT swallow API/admin/media/static
    # so Django's APPEND_SLASH redirect and existing routes still fire.
    re_path(r"^(?!api/|admin/|media/|static/|quick/).*$", spa.spa_index),
]
