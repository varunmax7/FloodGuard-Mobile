from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("reports", "0003_floodreport_party_size"),
    ]

    operations = [
        migrations.AddField(
            model_name="floodreport",
            name="description",
            field=models.TextField(blank=True, default=""),
        ),
    ]
