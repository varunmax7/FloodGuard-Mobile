"""Add role field to User for admin dashboard RBAC."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("accounts", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="user",
            name="role",
            field=models.CharField(
                choices=[
                    ("ADMIN", "Admin"),
                    ("OPERATOR", "Operator"),
                    ("VIEWER", "Viewer"),
                ],
                default="VIEWER",
                max_length=10,
            ),
        ),
    ]
