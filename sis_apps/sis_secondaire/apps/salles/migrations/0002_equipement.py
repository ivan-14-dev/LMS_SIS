# Generated for the SIS Secondaire equipment register.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("salles", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Equipement",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("identifiant", models.CharField(max_length=50)),
                ("nom", models.CharField(max_length=100)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "etablissement",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="equipements_salles",
                        to="etablissement.etablissement",
                    ),
                ),
                (
                    "salle",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="materiel",
                        to="salles.salle",
                    ),
                ),
            ],
            options={
                "ordering": ["identifiant"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("etablissement", "identifiant"),
                        name="salles_equipement_identifiant_unique",
                    ),
                ],
            },
        ),
    ]
