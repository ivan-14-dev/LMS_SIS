import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("classes", "0003_programmematiere_credits_and_more"),
        ("eleves", "0002_initial"),
        ("etablissement", "0003_etablissement_configuration_academique_and_more"),
        ("utilisateurs", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="AffectationMatiereIndividuelle",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("coefficient", models.DecimalField(decimal_places=2, default=1, max_digits=4)),
                ("credits", models.DecimalField(decimal_places=2, default=0, max_digits=6)),
                ("heures_semaine", models.DecimalField(decimal_places=2, default=0, max_digits=4)),
                ("obligatoire", models.BooleanField(default=True)),
                ("commentaire", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "annee_scolaire",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="affectations_matiere_individuelles",
                        to="etablissement.anneescolaire",
                    ),
                ),
                (
                    "eleve",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="affectations_matiere_individuelles",
                        to="eleves.eleve",
                    ),
                ),
                (
                    "enseignant_principal",
                    models.ForeignKey(
                        blank=True,
                        limit_choices_to={"role": "enseignant"},
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="affectations_individuelles_principales",
                        to="utilisateurs.utilisateur",
                    ),
                ),
                (
                    "enseignants",
                    models.ManyToManyField(
                        blank=True,
                        limit_choices_to={"role": "enseignant"},
                        related_name="affectations_individuelles_secondaire",
                        to="utilisateurs.utilisateur",
                    ),
                ),
                (
                    "matiere",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="affectations_individuelles",
                        to="classes.matiere",
                    ),
                ),
                (
                    "programme_source",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="affectations_individuelles",
                        to="classes.programmematiere",
                    ),
                ),
            ],
            options={
                "verbose_name": "Affectation matière individuelle",
                "verbose_name_plural": "Affectations matières individuelles",
                "ordering": ["annee_scolaire__date_debut", "matiere__nom"],
                "unique_together": {("eleve", "annee_scolaire", "matiere")},
            },
        )
    ]
