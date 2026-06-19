"""risk/models.py — RiskSnapshot, BiasFactor, CalibrationLog stubs."""
from django.db import models
from apps.geo.models import HexCell


class RiskSnapshot(models.Model):
    """Computed risk level for a hex cell at a given time."""
    LEVEL_CHOICES = [
        ("LOW", "Low"),
        ("MODERATE", "Moderate"),
        ("HIGH", "High"),
        ("SEVERE", "Severe"),
    ]

    hex = models.ForeignKey(HexCell, on_delete=models.CASCADE, related_name="snapshots")
    ts = models.DateTimeField(db_index=True)
    rain_1h = models.FloatField(null=True, blank=True)
    rain_3h = models.FloatField(null=True, blank=True)
    rain_24h = models.FloatField(null=True, blank=True)
    hazard_class = models.CharField(max_length=10, choices=LEVEL_CHOICES)
    risk_level = models.CharField(max_length=10, choices=LEVEL_CHOICES)
    confidence = models.IntegerField(default=0)  # 0..100
    source_model = models.CharField(max_length=50, default="ECMWF")

    class Meta:
        db_table = "risk_snapshot"
        ordering = ["-ts"]
        constraints = [
            models.UniqueConstraint(fields=["hex", "ts"], name="risk_snapshot_hex_ts_uniq"),
        ]
        indexes = [
            models.Index(fields=["ts", "risk_level"]),
        ]

    def __str__(self):
        return f"Snapshot({self.hex_id}, {self.ts}, {self.risk_level})"


class BiasFactor(models.Model):
    """Bias correction factor for a station/region."""
    station_id = models.CharField(max_length=50, blank=True, default="")  # empty = region-wide
    region = models.CharField(max_length=100, blank=True, default="")
    multiplier = models.FloatField(default=1.0)
    offset = models.FloatField(default=0.0)
    valid_from = models.DateTimeField()
    computed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "risk_bias_factor"
        ordering = ["-valid_from"]

    def __str__(self):
        return f"BiasFactor({self.station_id or self.region})"


class CalibrationLog(models.Model):
    """Audit trail for calibration changes."""
    actor = models.CharField(max_length=200)
    change_type = models.CharField(max_length=100)
    before = models.JSONField()
    after = models.JSONField()
    ts = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "risk_calibration_log"
        ordering = ["-ts"]

    def __str__(self):
        return f"CalLog({self.change_type}, {self.ts})"
