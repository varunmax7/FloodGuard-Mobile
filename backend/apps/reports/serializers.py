"""reports/serializers.py — public fields for flood reports."""
from django.utils import timezone
from rest_framework import serializers
from .models import FloodReport


class FloodReportPublicSerializer(serializers.ModelSerializer):
    lat = serializers.SerializerMethodField()
    lng = serializers.SerializerMethodField()
    time_ago = serializers.SerializerMethodField()

    class Meta:
        model = FloodReport
        fields = [
            "id", "depth", "road", "status",
            "photo_url", "observed_at", "created_at",
            "lat", "lng", "time_ago", "party_size",
        ]

    def get_lat(self, obj) -> float | None:
        return obj.geom.y if obj.geom else None

    def get_lng(self, obj) -> float | None:
        return obj.geom.x if obj.geom else None

    def get_time_ago(self, obj) -> str:
        diff = timezone.now() - obj.observed_at
        minutes = int(diff.total_seconds() / 60)
        if minutes < 1:
            return "just now"
        if minutes < 60:
            return f"{minutes}m ago"
        hours = minutes // 60
        if hours < 24:
            return f"{hours}h ago"
        return f"{hours // 24}d ago"
