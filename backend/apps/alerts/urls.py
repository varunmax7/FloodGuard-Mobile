"""alerts/urls.py"""
from django.urls import path
from . import views

urlpatterns = [
    path("", views.alerts_list, name="alerts-list"),
]
