"""ingest initial migration — RadarFrame."""
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="RadarFrame",
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
                ("ts", models.DateTimeField(db_index=True, unique=True)),
                ("tile_url_template", models.TextField()),
                ("dbz_min", models.FloatField(default=0.0)),
                ("dbz_max", models.FloatField(default=75.0)),
                ("georef_ok", models.BooleanField(default=True)),
            ],
            options={
                "db_table": "ingest_radar_frame",
                "ordering": ["-ts"],
            },
        ),
    ]
