"""Add source + report FK to AlertEvent."""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("alerts", "0001_initial"),
        ("reports", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="alertevent",
            name="source",
            field=models.CharField(
                choices=[("RISK", "Risk engine"), ("REPORT", "Verified user report")],
                default="RISK",
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="alertevent",
            name="report",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="alert_events",
                to="reports.floodreport",
            ),
        ),
    ]
