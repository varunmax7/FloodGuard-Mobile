"""ingest/models.py — RadarFrame model stub."""
from django.db import models


class RadarFrame(models.Model):
    """A processed radar frame ready to serve as a tile layer."""
    ts = models.DateTimeField(db_index=True, unique=True)
    tile_url_template = models.TextField()          # e.g. https://cdn/.../radar/{z}/{x}/{y}.png
    dbz_min = models.FloatField(default=0.0)
    dbz_max = models.FloatField(default=75.0)
    georef_ok = models.BooleanField(default=True)   # false if geo-registration failed

    class Meta:
        db_table = "ingest_radar_frame"
        ordering = ["-ts"]

    def __str__(self):
        return f"RadarFrame({self.ts})"
