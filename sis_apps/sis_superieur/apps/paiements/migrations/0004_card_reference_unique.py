from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("paiements", "0003_paiementfrais_motif_rejet_and_more"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="paiementfrais",
            constraint=models.UniqueConstraint(
                fields=["reference_externe"],
                condition=models.Q(mode="carte", statut__in=["valide", "rembourse"]) & ~models.Q(reference_externe=""),
                name="superieur_card_reference_once",
            ),
        ),
    ]
