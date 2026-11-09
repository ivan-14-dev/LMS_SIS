from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("etudiants", "0005_learning_offering_bindings")]

    operations = [
        migrations.AlterField(
            model_name="inscriptionadministrative",
            name="statut",
            field=models.CharField(
                choices=[
                    ("provisoire", "Provisoire"),
                    ("validee", "Validée"),
                    ("refusee", "Refusée"),
                    ("annulee", "Annulée"),
                    ("suspendue", "Suspendue"),
                    ("abandonnee", "Abandonnée"),
                ],
                default="provisoire",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="inscriptionadministrative",
            name="statut_apprenant_avant_interruption",
            field=models.CharField(blank=True, editable=False, max_length=20),
        ),
    ]
