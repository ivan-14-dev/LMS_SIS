import uuid

from django.contrib.postgres.functions import RandomUUID
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("utilisateurs", "0004_alter_utilisateur_mfa_secret"),
    ]

    operations = [
        migrations.AddField(
            model_name="utilisateur",
            name="integration_id",
            field=models.UUIDField(default=uuid.uuid4, db_default=RandomUUID(), editable=False, unique=True),
        ),
    ]
