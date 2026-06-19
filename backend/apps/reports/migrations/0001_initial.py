"""reports initial migration — FloodReport, ModerationLog."""
import django.contrib.gis.db.models.fields
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
            name="FloodReport",
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
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="reports",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "geom",
                    django.contrib.gis.db.models.fields.PointField(srid=4326),
                ),
                (
                    "hex",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="reports",
                        to="geo.hexcell",
                    ),
                ),
                ("photo_url", models.URLField(blank=True, default="")),
                (
                    "depth",
                    models.CharField(
                        choices=[
                            ("ANKLE", "Ankle"),
                            ("KNEE", "Knee"),
                            ("WAIST", "Waist"),
                            ("VEHICLE", "Vehicle level"),
                        ],
                        max_length=10,
                    ),
                ),
                (
                    "road",
                    models.CharField(
                        choices=[
                            ("PASSABLE", "Passable"),
                            ("DIFFICULT", "Difficult"),
                            ("BLOCKED", "Blocked"),
                        ],
                        max_length=10,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("PENDING", "Pending"),
                            ("VERIFIED", "Verified"),
                            ("REJECTED", "Rejected"),
                            ("SPAM", "Spam"),
                        ],
                        default="PENDING",
                        max_length=10,
                    ),
                ),
                ("observed_at", models.DateTimeField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("client_uuid", models.UUIDField(unique=True)),
            ],
            options={
                "db_table": "reports_flood_report",
                "ordering": ["-observed_at"],
                "indexes": [
                    models.Index(fields=["status"], name="reports_fr_status_idx"),
                    models.Index(
                        fields=["observed_at"], name="reports_fr_observed_idx"
                    ),
                    models.Index(
                        fields=["hex", "created_at"], name="reports_fr_hex_created_idx"
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="ModerationLog",
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
                    "actor",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "report",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="moderation_logs",
                        to="reports.floodreport",
                    ),
                ),
                ("action", models.CharField(max_length=20)),
                ("ts", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "db_table": "reports_moderation_log",
                "ordering": ["-ts"],
            },
        ),
    ]
