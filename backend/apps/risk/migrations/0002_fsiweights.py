from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("risk", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="FsiWeights",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("twi",               models.FloatField(default=0.25)),
                ("depression_depth",  models.FloatField(default=0.20)),
                ("hand",              models.FloatField(default=0.20)),
                ("dist_to_water",     models.FloatField(default=0.15)),
                ("slope",             models.FloatField(default=0.10)),
                ("imperviousness",    models.FloatField(default=0.10)),
                ("threshold_low",     models.FloatField(default=0.25)),
                ("threshold_moderate",models.FloatField(default=0.50)),
                ("threshold_high",    models.FloatField(default=0.75)),
                ("hazard_low",        models.FloatField(default=5.0)),
                ("hazard_moderate",   models.FloatField(default=15.0)),
                ("hazard_high",       models.FloatField(default=30.0)),
                ("updated_at",        models.DateTimeField(auto_now_add=True)),
                ("updated_by",        models.CharField(blank=True, max_length=200)),
            ],
            options={"db_table": "risk_fsi_weights", "ordering": ["-updated_at"]},
        ),
    ]
