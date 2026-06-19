"""alerts/models.py — AlertEvent, AlertDelivery models."""
import uuid
from django.db import models
from django.conf import settings
from apps.geo.models import HexCell


class AlertEvent(models.Model):
    """A flood alert event covering a hex area."""
    LEVEL_CHOICES = [
        ("LOW", "Low"),
        ("MODERATE", "Moderate"),
        ("HIGH", "High"),
        ("SEVERE", "Severe"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hex = models.ForeignKey(HexCell, on_delete=models.SET_NULL, null=True, blank=True,
                            related_name="alert_events")
    risk_level = models.CharField(max_length=10, choices=LEVEL_CHOICES)
    window_start = models.DateTimeField()
    window_end = models.DateTimeField()
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "alerts_event"
        ordering = ["-window_start"]
        indexes = [
            models.Index(fields=["risk_level", "window_start"]),
        ]

    def __str__(self):
        return f"Alert({self.risk_level}, {self.window_start})"


class AlertDelivery(models.Model):
    """FCM delivery record for an alert event to a specific user."""
    STATUS_CHOICES = [
        ("QUEUED", "Queued"),
        ("SENT", "Sent"),
        ("DELIVERED", "Delivered"),
        ("FAILED", "Failed"),
    ]

    alert = models.ForeignKey(AlertEvent, on_delete=models.CASCADE, related_name="deliveries")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="alert_deliveries")
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)  # FCM receipt
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="QUEUED")

    class Meta:
        db_table = "alerts_delivery"
        constraints = [
            models.UniqueConstraint(fields=["alert", "user"], name="alerts_delivery_alert_user_uniq"),
        ]

    def __str__(self):
        return f"Delivery({self.alert_id}, {self.user_id}, {self.status})"
