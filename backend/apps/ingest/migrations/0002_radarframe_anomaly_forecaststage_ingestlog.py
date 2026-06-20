"""ingest migration 0002 — anomaly field on RadarFrame, ForecastStage, IngestLog."""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ingest", "0001_initial"),
        ("geo", "0001_initial"),
    ]

    operations = [
        # Add anomaly flag to existing RadarFrame
        migrations.AddField(
            model_name="radarframe",
            name="anomaly",
            field=models.BooleanField(default=False),
        ),
        # New: ForecastStage
        migrations.CreateModel(
            name="ForecastStage",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "hex",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="forecasts",
                        to="geo.hexcell",
                    ),
                ),
                ("valid_ts", models.DateTimeField()),
                ("run_ts", models.DateTimeField()),
                ("rain_1h", models.FloatField(blank=True, null=True)),
                ("rain_3h", models.FloatField(blank=True, null=True)),
                ("rain_24h", models.FloatField(blank=True, null=True)),
                ("source", models.CharField(default="ECMWF", max_length=50)),
            ],
            options={
                "db_table": "ingest_forecast_stage",
                "indexes": [
                    models.Index(fields=["valid_ts", "hex"], name="ingest_fcast_vts_hex_idx"),
                    models.Index(fields=["run_ts"], name="ingest_fcast_run_ts_idx"),
                ],
            },
        ),
        migrations.AddConstraint(
            model_name="forecaststage",
            constraint=models.UniqueConstraint(
                fields=["hex", "valid_ts", "run_ts", "source"],
                name="ingest_fcast_hex_ts_run_src_uniq",
            ),
        ),
        # New: IngestLog
        migrations.CreateModel(
            name="IngestLog",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "feed",
                    models.CharField(
                        choices=[
                            ("ecmwf", "ECMWF Forecast"),
                            ("aws", "AWS Rain Gauge"),
                            ("radar", "Radar Frames"),
                            ("bias", "Bias Recompute"),
                        ],
                        max_length=20,
                        unique=True,
                    ),
                ),
                ("last_success", models.DateTimeField(blank=True, null=True)),
                ("last_attempted", models.DateTimeField(blank=True, null=True)),
                ("last_error", models.TextField(blank=True, default="")),
                ("records_written", models.IntegerField(default=0)),
            ],
            options={
                "db_table": "ingest_log",
            },
        ),
    ]
