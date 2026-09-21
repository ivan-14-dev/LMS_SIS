"""API tests for paiements."""

from decimal import Decimal
from types import SimpleNamespace

from apps.paiements.serializers import PaiementCreateSerializer
from django.test import SimpleTestCase
from django.urls import resolve
from rest_framework.exceptions import ValidationError


class EmptyGuardianLinks:
    def filter(self, **kwargs):
        return self

    def exists(self):
        return False


class PaiementsAPITestCase(SimpleTestCase):
    def test_finance_history_routes_are_registered(self):
        invoice_history = resolve("/api/v1/paiements/factures/1/historique/")
        payment_history = resolve("/api/v1/paiements/transactions/1/historique/")

        self.assertEqual(invoice_history.url_name, "facture-historique")
        self.assertEqual(payment_history.url_name, "paiement-historique")

    def test_user_cannot_submit_payment_for_another_pupil(self):
        user = SimpleNamespace(id=1, is_staff=False, role="parent", has_perm=lambda permission: False)
        invoice = SimpleNamespace(
            statut="emise",
            montant=Decimal("100"),
            montant_paye=Decimal("0"),
            montant_restant=Decimal("100"),
            eleve=SimpleNamespace(user_id=2, tuteurs_lies=EmptyGuardianLinks()),
        )
        serializer = PaiementCreateSerializer(context={"request": SimpleNamespace(user=user)})

        with self.assertRaisesMessage(ValidationError, "Vous ne pouvez pas payer cette facture"):
            serializer.validate({"facture": invoice, "montant": Decimal("10")})
