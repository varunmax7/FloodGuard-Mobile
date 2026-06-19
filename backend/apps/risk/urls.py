"""risk/urls.py"""
from django.urls import path
from . import views

urlpatterns = [
    path("hexes/", views.risk_hexes, name="risk-hexes"),
    path("location/", views.risk_location, name="risk-location"),
    path("overview/", views.risk_overview, name="risk-overview"),
]
