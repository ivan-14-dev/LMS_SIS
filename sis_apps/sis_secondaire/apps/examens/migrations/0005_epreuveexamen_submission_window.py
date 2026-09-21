from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("examens", "0004_sessionexamen_cloturee_resultatexamen_workflow"),
    ]

    operations = [
        migrations.AddField(
            model_name="epreuveexamen",
            name="debut_soumission",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="epreuveexamen",
            name="fin_soumission",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
