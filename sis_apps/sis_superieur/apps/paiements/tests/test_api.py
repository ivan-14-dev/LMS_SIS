"""API tests for paiements."""

from decimal import Decimal
from types import SimpleNamespace

from apps.paiements.serializers import PaiementCreateSerializer
from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError


class PaiementsAPITestCase(SimpleTestCase):
    def test_student_cannot_submit_payment_for_another_student(self):
        user = SimpleNamespace(id=1, is_staff=False, role="etudiant", has_perm=lambda permission: False)
        invoice = SimpleNamespace(
            statut="emise",
            montant=Decimal("100"),
            montant_paye=Decimal("0"),
            etudiant=SimpleNamespace(user_id=2),
        )
        serializer = PaiementCreateSerializer(context={"request": SimpleNamespace(user=user)})

        with self.assertRaisesMessage(ValidationError, "Vous ne pouvez pas payer cette facture"):
            serializer.validate({"facture": invoice, "montant": Decimal("10")})
