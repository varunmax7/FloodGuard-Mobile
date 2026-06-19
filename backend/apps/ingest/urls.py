"""ingest/urls.py"""
from django.urls import path
from . import views

urlpatterns = [
    path("frames/", views.radar_frames, name="radar-frames"),
]
