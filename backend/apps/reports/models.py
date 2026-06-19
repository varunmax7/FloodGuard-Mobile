"""reports/models.py — FloodReport, ModerationLog models."""
import uuid
from django.contrib.gis.db import models
from django.conf import settings
from apps.geo.models import HexCell


class FloodReport(models.Model):
    """Crowd-sourced flood report submitted by a user."""
    DEPTH_CHOICES = [
        ("ANKLE", "Ankle"),
        ("KNEE", "Knee"),
        ("WAIST", "Waist"),
        ("VEHICLE", "Vehicle level"),
    ]
    ROAD_CHOICES = [
        ("PASSABLE", "Passable"),
        ("DIFFICULT", "Difficult"),
        ("BLOCKED", "Blocked"),
    ]
    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("VERIFIED", "Verified"),
        ("REJECTED", "Rejected"),
        ("SPAM", "Spam"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="reports"
    )
    geom = models.PointField(srid=4326)
    hex = models.ForeignKey(HexCell, on_delete=models.SET_NULL, null=True, blank=True,
                            related_name="reports")
    photo_url = models.URLField(blank=True, default="")
    depth = models.CharField(max_length=10, choices=DEPTH_CHOICES)
    road = models.CharField(max_length=10, choices=ROAD_CHOICES)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="PENDING")
    observed_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    client_uuid = models.UUIDField(unique=True)     # idempotency key from client

    class Meta:
        db_table = "reports_flood_report"
        ordering = ["-observed_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["observed_at"]),
        ]

    def __str__(self):
        return f"Report({self.id}, {self.depth}, {self.status})"


class ModerationLog(models.Model):
    """Audit trail for moderation actions."""
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )
    report = models.ForeignKey(FloodReport, on_delete=models.CASCADE, related_name="moderation_logs")
    action = models.CharField(max_length=20)    # verify|reject|spam
    ts = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "reports_moderation_log"
        ordering = ["-ts"]

    def __str__(self):
        return f"ModLog({self.action}, {self.ts})"
