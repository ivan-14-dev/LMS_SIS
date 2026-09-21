import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("etablissement", "0003_initial"),
        ("etudiants", "0002_initial"),
        ("ue_ecue", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="AffectationECUEIndividuelle",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("obligatoire", models.BooleanField(default=True)),
                ("groupe_td", models.CharField(blank=True, max_length=20)),
                ("groupe_tp", models.CharField(blank=True, max_length=20)),
                ("commentaire", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "ecue",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="affectations_etudiant_individuelles",
                        to="ue_ecue.ecue",
                    ),
                ),
                (
                    "inscription_admin",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="affectations_ecue_individuelles",
                        to="etudiants.inscriptionadministrative",
                    ),
                ),
                (
                    "semestre_cible",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="affectations_ecue_individuelles",
                        to="etablissement.semestre",
                    ),
                ),
            ],
            options={
                "verbose_name": "Affectation ECUE individuelle",
                "verbose_name_plural": "Affectations ECUE individuelles",
                "ordering": [
                    "semestre_cible__annee_universitaire",
                    "semestre_cible__numero",
                    "ecue__code",
                ],
                "unique_together": {("inscription_admin", "semestre_cible", "ecue")},
            },
        )
    ]
