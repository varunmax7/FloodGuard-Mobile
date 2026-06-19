"""reports/admin.py — Django admin for FloodReport, ModerationLog."""
from django.contrib.gis import admin
from .models import FloodReport, ModerationLog


@admin.register(FloodReport)
class FloodReportAdmin(admin.GISModelAdmin):
    list_display = ("id", "depth", "road", "status", "observed_at", "created_at")
    list_filter = ("status", "depth", "road")
    search_fields = ("id", "user__phone")
    ordering = ("-observed_at",)
    date_hierarchy = "observed_at"
    readonly_fields = ("id", "client_uuid", "created_at")


@admin.register(ModerationLog)
class ModerationLogAdmin(admin.ModelAdmin):
    list_display = ("actor", "report", "action", "ts")
    list_filter = ("action",)
    ordering = ("-ts",)
    readonly_fields = ("actor", "report", "action", "ts")
