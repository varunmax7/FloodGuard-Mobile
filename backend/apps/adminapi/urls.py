"""adminapi/urls.py — stub routes for Phases 10-12."""
from django.urls import path
from . import views

urlpatterns = [
    path("health/feeds/", views.health_feeds, name="admin-health-feeds"),
]
