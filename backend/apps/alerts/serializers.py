"""alerts/serializers.py"""
from rest_framework import serializers
from .models import AlertEvent, AlertDelivery


class AlertEventSerializer(serializers.ModelSerializer):
    h3_index = serializers.SerializerMethodField()
    ward_name = serializers.SerializerMethodField()
    is_active = serializers.SerializerMethodField()
    photo_url = serializers.SerializerMethodField()
    depth = serializers.SerializerMethodField()
    road = serializers.SerializerMethodField()
    lat = serializers.SerializerMethodField()
    lon = serializers.SerializerMethodField()

    class Meta:
        model = AlertEvent
        fields = [
            "id", "risk_level", "source", "message",
            "window_start", "window_end", "created_at",
            "h3_index", "ward_name", "is_active",
            "photo_url", "depth", "road", "lat", "lon",
        ]

    def get_h3_index(self, obj):
        return obj.hex.h3_index if obj.hex else None

    def get_ward_name(self, obj):
        return obj.hex.ward_name if obj.hex else None

    def get_is_active(self, obj):
        from django.utils import timezone
        return obj.window_end >= timezone.now()

    def get_photo_url(self, obj):
        return obj.report.photo_url if obj.report else None

    def get_depth(self, obj):
        return obj.report.depth if obj.report else None

    def get_road(self, obj):
        return obj.report.road if obj.report else None

    def get_lat(self, obj):
        if obj.report:
            return obj.report.geom.y
        return obj.hex.centroid.y if obj.hex and obj.hex.centroid else None

    def get_lon(self, obj):
        if obj.report:
            return obj.report.geom.x
        return obj.hex.centroid.x if obj.hex and obj.hex.centroid else None


class AlertDeliverySerializer(serializers.ModelSerializer):
    class Meta:
        model = AlertDelivery
        fields = ["id", "status", "sent_at", "delivered_at"]
