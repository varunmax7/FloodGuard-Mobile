"""accounts/places_urls.py — saved places routes."""
from django.urls import path
from rest_framework.decorators import api_view
from rest_framework.response import Response


@api_view(["GET", "POST"])
def places_list(request):
    return Response({"detail": "Not implemented yet — Phase 5"}, status=501)


@api_view(["PATCH"])
def place_detail(request, pk):
    return Response({"detail": "Not implemented yet — Phase 5"}, status=501)


urlpatterns = [
    path("", places_list, name="places-list"),
    path("<int:pk>/", place_detail, name="place-detail"),
]
