"""accounts/devices_urls.py — /api/v1/devices/ routes."""
from django.urls import path
from .views import register_device_token

urlpatterns = [
    path("token/", register_device_token, name="device-token"),
]
