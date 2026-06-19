"""accounts/devices_urls.py — FCM token registration routes."""
from django.urls import path
from rest_framework.decorators import api_view
from rest_framework.response import Response


@api_view(["POST"])
def register_token(request):
    return Response({"detail": "Not implemented yet — Phase 5"}, status=501)


urlpatterns = [
    path("token/", register_token, name="device-token"),
]
