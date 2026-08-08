# Region migration: Assam → Telangana + Andhra Pradesh.
# District.name is no longer globally unique — TG and AP can each have a
# same-named district in theory, and uniqueness now spans (state, name).
# Also drops the "Assam" default on District.state.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('geo', '0003_district_taluka'),
    ]

    operations = [
        migrations.AlterField(
            model_name='district',
            name='name',
            field=models.CharField(max_length=64),
        ),
        migrations.AlterField(
            model_name='district',
            name='state',
            field=models.CharField(max_length=32),
        ),
        migrations.AlterModelOptions(
            name='district',
            options={'ordering': ['state', 'name']},
        ),
        migrations.AddConstraint(
            model_name='district',
            constraint=models.UniqueConstraint(
                fields=('state', 'name'),
                name='geo_district_state_name_uniq',
            ),
        ),
        migrations.AddIndex(
            model_name='district',
            index=models.Index(fields=['state'], name='geo_distric_state_idx'),
        ),
    ]
