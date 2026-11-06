import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("paiements", "0004_card_reference_unique"),
        ("etablissement", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="BudgetPrevisionnel",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=50)),
                ("libelle", models.CharField(max_length=200)),
                ("montant_prevu", models.DecimalField(decimal_places=2, max_digits=12)),
                (
                    "statut",
                    models.CharField(
                        choices=[("ouvert", "Ouvert"), ("cloture", "Clôturé")],
                        default="ouvert",
                        max_length=10,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "annee_scolaire",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="budgets_previsionnels",
                        to="etablissement.anneescolaire",
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("annee_scolaire", "code"), name="secondaire_budget_year_code"
                    ),
                    models.CheckConstraint(
                        condition=models.Q(montant_prevu__gt=0), name="secondaire_budget_positive"
                    ),
                ],
            },
        ),
    ]
