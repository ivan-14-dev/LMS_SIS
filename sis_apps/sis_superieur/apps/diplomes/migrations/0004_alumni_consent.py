import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("diplomes", "0003_initial"),
        ("etudiants", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="cessiondiplome",
            name="date_revocation",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name="ConsentementAlumni",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("actif", models.BooleanField(default=False)),
                ("revision", models.PositiveIntegerField(default=0)),
                ("consenti_le", models.DateTimeField(blank=True, null=True)),
                ("retire_le", models.DateTimeField(blank=True, null=True)),
                (
                    "etudiant",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="consentement_alumni",
                        to="etudiants.etudiant",
                    ),
                ),
            ],
            options={
                "verbose_name": "Consentement alumni",
                "verbose_name_plural": "Consentements alumni",
            },
        ),
    ]
