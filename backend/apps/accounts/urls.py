"""accounts/urls.py — OTP auth routes."""
from django.urls import path
from . import views

urlpatterns = [
    path("otp/request/", views.otp_request, name="otp-request"),
    path("otp/verify/", views.otp_verify, name="otp-verify"),
]
