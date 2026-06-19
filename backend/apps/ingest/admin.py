"""ingest/admin.py — Django admin for RadarFrame."""
from django.contrib import admin
from .models import RadarFrame


@admin.register(RadarFrame)
class RadarFrameAdmin(admin.ModelAdmin):
    list_display = ("ts", "dbz_min", "dbz_max", "georef_ok")
    list_filter = ("georef_ok",)
    ordering = ("-ts",)
    date_hierarchy = "ts"
    readonly_fields = ("ts",)
