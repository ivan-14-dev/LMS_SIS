from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("eleves", "0006_learning_offering_bindings")]

    operations = [
        migrations.AlterField(
            model_name="eleve",
            name="statut",
            field=models.CharField(
                choices=[
                    ("inscrit", "Inscrit"),
                    ("redoublant", "Redoublant"),
                    ("suspendu", "Suspendu"),
                    ("sortant", "Sortant"),
                    ("transfere", "Transféré"),
                    ("diplome", "Diplômé"),
                    ("abandon", "Abandon"),
                ],
                default="inscrit",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="inscription",
            name="statut",
            field=models.CharField(
                choices=[
                    ("en_cours", "En cours"),
                    ("validee", "Validée"),
                    ("refusee", "Refusée"),
                    ("annulee", "Annulée"),
                    ("suspendue", "Suspendue"),
                    ("abandonnee", "Abandonnée"),
                ],
                default="en_cours",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="inscription",
            name="statut_apprenant_avant_interruption",
            field=models.CharField(blank=True, editable=False, max_length=20),
        ),
    ]
