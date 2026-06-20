"""ingest/admin.py — Django admin for RadarFrame, ForecastStage, IngestLog."""
from django.contrib import admin
from .models import ForecastStage, IngestLog, RadarFrame


@admin.register(RadarFrame)
class RadarFrameAdmin(admin.ModelAdmin):
    list_display = ("ts", "dbz_min", "dbz_max", "georef_ok", "anomaly")
    list_filter = ("georef_ok", "anomaly")
    ordering = ("-ts",)
    date_hierarchy = "ts"
    readonly_fields = ("ts",)


@admin.register(ForecastStage)
class ForecastStageAdmin(admin.ModelAdmin):
    list_display = ("hex_id", "valid_ts", "run_ts", "rain_1h", "rain_3h", "rain_24h", "source")
    list_filter = ("source",)
    ordering = ("-valid_ts",)
    date_hierarchy = "valid_ts"
    search_fields = ("hex__h3_index",)


@admin.register(IngestLog)
class IngestLogAdmin(admin.ModelAdmin):
    list_display = ("feed", "last_success", "last_attempted", "records_written", "last_error_short")
    ordering = ("feed",)
    readonly_fields = ("feed", "last_success", "last_attempted", "records_written", "last_error")

    def last_error_short(self, obj):
        return obj.last_error[:80] if obj.last_error else "—"
    last_error_short.short_description = "Last Error"
