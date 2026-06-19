"""alerts/admin.py — Django admin for AlertEvent, AlertDelivery."""
from django.contrib import admin
from .models import AlertDelivery, AlertEvent


@admin.register(AlertEvent)
class AlertEventAdmin(admin.ModelAdmin):
    list_display = ("id", "risk_level", "hex_id", "window_start", "window_end")
    list_filter = ("risk_level",)
    ordering = ("-window_start",)
    date_hierarchy = "window_start"
    readonly_fields = ("id", "created_at")


@admin.register(AlertDelivery)
class AlertDeliveryAdmin(admin.ModelAdmin):
    list_display = ("alert", "user", "status", "sent_at", "delivered_at")
    list_filter = ("status",)
    ordering = ("-sent_at",)
    readonly_fields = ("alert", "user", "sent_at", "delivered_at", "status")
