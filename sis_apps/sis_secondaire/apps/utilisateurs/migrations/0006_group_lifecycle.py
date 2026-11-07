import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        ("utilisateurs", "0005_utilisateur_integration_id"),
    ]

    operations = [
        migrations.CreateModel(
            name="GroupLifecycle",
            fields=[
                (
                    "group",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        primary_key=True,
                        related_name="permission_lifecycle",
                        serialize=False,
                        to="auth.group",
                    ),
                ),
                ("actif", models.BooleanField(default=True)),
            ],
            options={"default_permissions": ()},
        ),
    ]
