import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("salles", "0002_equipement"),
    ]

    operations = [
        migrations.CreateModel(
            name="IndisponibiliteSalle",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("date_debut", models.DateField()),
                ("date_fin", models.DateField()),
                ("motif", models.CharField(blank=True, max_length=200)),
                (
                    "salle",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="indisponibilites",
                        to="salles.salle",
                    ),
                ),
            ],
            options={
                "ordering": ["date_debut", "id"],
                "indexes": [
                    models.Index(
                        fields=["salle", "date_debut", "date_fin"],
                        name="salles_indisp_dates_idx",
                    )
                ],
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(date_fin__gte=models.F("date_debut")),
                        name="salles_indisponibilite_dates_valides",
                    ),
                ],
            },
        ),
    ]
