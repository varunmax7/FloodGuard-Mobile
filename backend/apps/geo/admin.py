"""geo/admin.py — Django admin for HexCell, AwsStation, AwsObservation."""
from django.contrib.gis import admin
from .models import AwsObservation, AwsStation, HexCell


@admin.register(HexCell)
class HexCellAdmin(admin.GISModelAdmin):
    list_display = ("h3_index", "ward_name", "fsi_score")
    list_filter = ("ward_name",)
    search_fields = ("h3_index", "ward_name")
    readonly_fields = ("h3_index", "fsi_score", "fsi_inputs")
    ordering = ("h3_index",)


@admin.register(AwsStation)
class AwsStationAdmin(admin.GISModelAdmin):
    list_display = ("station_id", "name", "hex_id")
    search_fields = ("station_id", "name")


@admin.register(AwsObservation)
class AwsObservationAdmin(admin.ModelAdmin):
    list_display = ("station", "ts", "rain_1h", "rain_3h", "rain_24h")
    list_filter = ("station",)
    ordering = ("-ts",)
    date_hierarchy = "ts"
