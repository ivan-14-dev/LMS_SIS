import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("bibliotheque", "0002_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="reservation",
            name="emprunt",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="reservation",
                to="bibliotheque.emprunt",
            ),
        ),
        migrations.AlterField(
            model_name="reservation",
            name="statut",
            field=models.CharField(
                choices=[
                    ("en_attente", "En attente"),
                    ("disponible", "Disponible"),
                    ("annulee", "Annulée"),
                    ("honoree", "Honorée"),
                ],
                default="en_attente",
                max_length=20,
            ),
        ),
        migrations.AddConstraint(
            model_name="reservation",
            constraint=models.UniqueConstraint(
                condition=models.Q(statut__in=["en_attente", "disponible"]),
                fields=("livre", "utilisateur"),
                name="bibliotheque_unique_active_reservation",
            ),
        ),
    ]
