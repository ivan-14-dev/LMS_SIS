from django.db import migrations, models

import sis_common.exam_files


class Migration(migrations.Migration):
    dependencies = [("paiements", "0004_card_reference_unique")]
    operations = [
        migrations.AddConstraint(
            model_name="paiementfrais",
            constraint=models.UniqueConstraint(
                fields=["mode", "reference_externe"],
                condition=models.Q(statut__in=["valide", "rembourse"]) & ~models.Q(reference_externe=""),
                name="superieur_payment_reference_once",
            ),
        ),
        migrations.AddField(
            model_name="facturefrais",
            name="devise",
            field=models.CharField(blank=True, default="", max_length=3),
        ),
        migrations.AddField(
            model_name="paiementfrais",
            name="remboursement",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="paiementfrais",
            name="preuve_remboursement",
            field=models.FileField(
                blank=True,
                null=True,
                storage=sis_common.exam_files.PrivateFinancialStorage(),
                upload_to=sis_common.exam_files.payment_proof_upload_to,
                validators=[sis_common.exam_files.validate_payment_proof],
            ),
        ),
        migrations.AlterField(
            model_name="paiementfrais",
            name="statut",
            field=models.CharField(
                choices=[
                    ("en_attente", "En attente"),
                    ("valide", "Validé"),
                    ("echec", "Échec"),
                    ("rejete", "Rejeté"),
                    ("rembourse", "Remboursé"),
                ],
                default="en_attente",
                max_length=20,
            ),
        ),
    ]
