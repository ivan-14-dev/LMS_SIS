from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0011_project_course")]

    operations = [
        migrations.AddField(
            model_name="pedagogicalproject",
            name="competences_snapshot",
            field=models.JSONField(blank=True, default=None, editable=False, null=True),
        ),
    ]
