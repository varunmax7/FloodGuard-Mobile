"""alerts initial migration — AlertEvent, AlertDelivery."""
import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("accounts", "0001_initial"),
        ("geo", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="AlertEvent",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "hex",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="alert_events",
                        to="geo.hexcell",
                    ),
                ),
                (
                    "risk_level",
                    models.CharField(
                        choices=[
                            ("LOW", "Low"),
                            ("MODERATE", "Moderate"),
                            ("HIGH", "High"),
                            ("SEVERE", "Severe"),
                        ],
                        max_length=10,
                    ),
                ),
                ("window_start", models.DateTimeField()),
                ("window_end", models.DateTimeField()),
                ("message", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "db_table": "alerts_event",
                "ordering": ["-window_start"],
                "indexes": [
                    models.Index(
                        fields=["risk_level", "window_start"],
                        name="alerts_ev_level_start_idx",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="AlertDelivery",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "alert",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="deliveries",
                        to="alerts.alertevent",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="alert_deliveries",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                ("delivered_at", models.DateTimeField(blank=True, null=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("QUEUED", "Queued"),
                            ("SENT", "Sent"),
                            ("DELIVERED", "Delivered"),
                            ("FAILED", "Failed"),
                        ],
                        default="QUEUED",
                        max_length=10,
                    ),
                ),
            ],
            options={
                "db_table": "alerts_delivery",
            },
        ),
        migrations.AddConstraint(
            model_name="alertdelivery",
            constraint=models.UniqueConstraint(
                fields=["alert", "user"], name="alerts_delivery_alert_user_uniq"
            ),
        ),
    ]
