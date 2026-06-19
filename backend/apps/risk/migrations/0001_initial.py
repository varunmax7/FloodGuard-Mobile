"""risk initial migration — RiskSnapshot, BiasFactor, CalibrationLog."""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("geo", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="RiskSnapshot",
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
                    "hex",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="snapshots",
                        to="geo.hexcell",
                    ),
                ),
                ("ts", models.DateTimeField(db_index=True)),
                ("rain_1h", models.FloatField(blank=True, null=True)),
                ("rain_3h", models.FloatField(blank=True, null=True)),
                ("rain_24h", models.FloatField(blank=True, null=True)),
                (
                    "hazard_class",
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
                ("confidence", models.IntegerField(default=0)),
                ("source_model", models.CharField(default="ECMWF", max_length=50)),
            ],
            options={
                "db_table": "risk_snapshot",
                "ordering": ["-ts"],
                "indexes": [
                    models.Index(
                        fields=["ts", "risk_level"], name="risk_snap_ts_level_idx"
                    ),
                ],
            },
        ),
        migrations.AddConstraint(
            model_name="risksnapshot",
            constraint=models.UniqueConstraint(
                fields=["hex", "ts"], name="risk_snapshot_hex_ts_uniq"
            ),
        ),
        migrations.CreateModel(
            name="BiasFactor",
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
                ("station_id", models.CharField(blank=True, default="", max_length=50)),
                ("region", models.CharField(blank=True, default="", max_length=100)),
                ("multiplier", models.FloatField(default=1.0)),
                ("offset", models.FloatField(default=0.0)),
                ("valid_from", models.DateTimeField()),
                ("computed_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "db_table": "risk_bias_factor",
                "ordering": ["-valid_from"],
            },
        ),
        migrations.CreateModel(
            name="CalibrationLog",
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
                ("actor", models.CharField(max_length=200)),
                ("change_type", models.CharField(max_length=100)),
                ("before", models.JSONField()),
                ("after", models.JSONField()),
                ("ts", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "db_table": "risk_calibration_log",
                "ordering": ["-ts"],
            },
        ),
    ]
