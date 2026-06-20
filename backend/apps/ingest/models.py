"""ingest/models.py — RadarFrame, ForecastStage, IngestLog."""
from django.db import models
from apps.geo.models import HexCell


class RadarFrame(models.Model):
    """A processed radar frame ready to serve as a tile layer."""
    ts = models.DateTimeField(db_index=True, unique=True)
    tile_url_template = models.TextField()
    dbz_min = models.FloatField(default=0.0)
    dbz_max = models.FloatField(default=75.0)
    georef_ok = models.BooleanField(default=True)
    anomaly = models.BooleanField(default=False)  # True if dBZ distribution is suspicious

    class Meta:
        db_table = "ingest_radar_frame"
        ordering = ["-ts"]

    def __str__(self):
        return f"RadarFrame({self.ts}, georef={self.georef_ok}, anomaly={self.anomaly})"


class ForecastStage(models.Model):
    """
    Staged ECMWF precipitation per hex cell.
    Phase 4 reads this to compute RiskSnapshot.
    """
    hex = models.ForeignKey(HexCell, on_delete=models.CASCADE, related_name="forecasts")
    valid_ts = models.DateTimeField()   # when the forecast is valid for
    run_ts = models.DateTimeField()     # model run time (e.g. 00Z, 06Z, 12Z, 18Z)
    rain_1h = models.FloatField(null=True, blank=True)   # mm/h
    rain_3h = models.FloatField(null=True, blank=True)   # mm/3h
    rain_24h = models.FloatField(null=True, blank=True)  # mm/24h
    source = models.CharField(max_length=50, default="ECMWF")

    class Meta:
        db_table = "ingest_forecast_stage"
        constraints = [
            models.UniqueConstraint(
                fields=["hex", "valid_ts", "run_ts", "source"],
                name="ingest_fcast_hex_ts_run_src_uniq",
            )
        ]
        indexes = [
            models.Index(fields=["valid_ts", "hex"]),
            models.Index(fields=["run_ts"]),
        ]

    def __str__(self):
        return f"ForecastStage({self.hex_id}, {self.valid_ts}, {self.source})"


class IngestLog(models.Model):
    """Records last-run metadata for each ingest feed."""
    FEED_CHOICES = [
        ("ecmwf", "ECMWF Forecast"),
        ("aws", "AWS Rain Gauge"),
        ("radar", "Radar Frames"),
        ("bias", "Bias Recompute"),
    ]

    feed = models.CharField(max_length=20, unique=True, choices=FEED_CHOICES)
    last_success = models.DateTimeField(null=True, blank=True)
    last_attempted = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True, default="")
    records_written = models.IntegerField(default=0)

    class Meta:
        db_table = "ingest_log"

    def __str__(self):
        return f"IngestLog({self.feed}, last_success={self.last_success})"
