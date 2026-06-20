"""alerts/serializers.py"""
from rest_framework import serializers
from .models import AlertEvent, AlertDelivery


class AlertEventSerializer(serializers.ModelSerializer):
    h3_index = serializers.SerializerMethodField()
    ward_name = serializers.SerializerMethodField()
    is_active = serializers.SerializerMethodField()

    class Meta:
        model = AlertEvent
        fields = [
            "id", "risk_level", "message",
            "window_start", "window_end", "created_at",
            "h3_index", "ward_name", "is_active",
        ]

    def get_h3_index(self, obj):
        return obj.hex.h3_index if obj.hex else None

    def get_ward_name(self, obj):
        return obj.hex.ward_name if obj.hex else None

    def get_is_active(self, obj):
        from django.utils import timezone
        return obj.window_end >= timezone.now()


class AlertDeliverySerializer(serializers.ModelSerializer):
    class Meta:
        model = AlertDelivery
        fields = ["id", "status", "sent_at", "delivered_at"]
