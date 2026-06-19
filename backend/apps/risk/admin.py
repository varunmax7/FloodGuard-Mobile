"""risk/admin.py — Django admin for RiskSnapshot, BiasFactor, CalibrationLog."""
from django.contrib import admin
from .models import BiasFactor, CalibrationLog, RiskSnapshot


@admin.register(RiskSnapshot)
class RiskSnapshotAdmin(admin.ModelAdmin):
    list_display = ("hex_id", "ts", "risk_level", "hazard_class", "confidence", "source_model")
    list_filter = ("risk_level", "hazard_class", "source_model")
    ordering = ("-ts",)
    date_hierarchy = "ts"
    search_fields = ("hex__h3_index",)


@admin.register(BiasFactor)
class BiasFactorAdmin(admin.ModelAdmin):
    list_display = ("station_id", "region", "multiplier", "offset", "valid_from", "computed_at")
    ordering = ("-valid_from",)


@admin.register(CalibrationLog)
class CalibrationLogAdmin(admin.ModelAdmin):
    list_display = ("actor", "change_type", "ts")
    list_filter = ("change_type",)
    ordering = ("-ts",)
    readonly_fields = ("actor", "change_type", "before", "after", "ts")
