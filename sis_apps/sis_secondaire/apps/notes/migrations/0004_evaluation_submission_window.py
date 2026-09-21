from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("notes", "0003_evaluation_eleve_cible"),
    ]

    operations = [
        migrations.AddField(
            model_name="evaluation",
            name="debut_soumission",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="evaluation",
            name="fin_soumission",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
