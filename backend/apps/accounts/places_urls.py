"""accounts/places_urls.py — /api/v1/places/ routes."""
from django.urls import path
from .views import place_detail, places_list

urlpatterns = [
    path("", places_list, name="places-list"),
    path("<int:pk>/", place_detail, name="place-detail"),
]
