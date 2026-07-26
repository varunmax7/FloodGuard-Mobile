"""geo initial migration — HexCell, AwsStation, AwsObservation."""
import django.contrib.gis.db.models.fields
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.RunSQL(
            "CREATE EXTENSION IF NOT EXISTS postgis",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.CreateModel(
            name="HexCell",
            fields=[
                ("h3_index", models.CharField(max_length=20, primary_key=True, serialize=False)),
                (
                    "geom",
                    django.contrib.gis.db.models.fields.PolygonField(
                        blank=True, null=True, srid=4326
                    ),
                ),
                (
                    "centroid",
                    django.contrib.gis.db.models.fields.PointField(
                        blank=True, null=True, srid=4326
                    ),
                ),
                ("fsi_inputs", models.JSONField(blank=True, default=dict)),
                ("fsi_score", models.FloatField(default=0.0)),
                ("ward_name", models.CharField(blank=True, default="", max_length=100)),
            ],
            options={
                "db_table": "geo_hex_cell",
                "indexes": [
                    models.Index(fields=["fsi_score"], name="geo_hex_cel_fsi_sco_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="AwsStation",
            fields=[
                (
                    "station_id",
                    models.CharField(max_length=50, primary_key=True, serialize=False),
                ),
                ("name", models.CharField(max_length=200)),
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
                        related_name="stations",
                        to="geo.hexcell",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "db_table": "geo_aws_station",
            },
        ),
        migrations.CreateModel(
            name="AwsObservation",
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
                    "station",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="observations",
                        to="geo.awsstation",
                    ),
                ),
                ("ts", models.DateTimeField(db_index=True)),
                ("rain_1h", models.FloatField(blank=True, null=True)),
                ("rain_3h", models.FloatField(blank=True, null=True)),
                ("rain_24h", models.FloatField(blank=True, null=True)),
            ],
            options={
                "db_table": "geo_aws_observation",
                "ordering": ["-ts"],
                "indexes": [
                    models.Index(
                        fields=["station", "ts"], name="geo_aws_obs_station_ts_idx"
                    ),
                ],
            },
        ),
        migrations.AddConstraint(
            model_name="awsobservation",
            constraint=models.UniqueConstraint(
                fields=["station", "ts"], name="geo_awsobs_station_ts_uniq"
            ),
        ),
    ]
