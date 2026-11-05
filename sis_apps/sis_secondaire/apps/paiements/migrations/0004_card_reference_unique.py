from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("paiements", "0003_paiement_motif_rejet_paiement_preuve_paiement_and_more"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="paiement",
            constraint=models.UniqueConstraint(
                fields=["reference_externe"],
                condition=models.Q(mode="carte", statut__in=["valide", "rembourse"]) & ~models.Q(reference_externe=""),
                name="secondaire_card_reference_once",
            ),
        ),
    ]
