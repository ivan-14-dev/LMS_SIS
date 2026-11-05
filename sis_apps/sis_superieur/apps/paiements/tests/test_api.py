"""API tests for paiements."""

from contextlib import nullcontext
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch

from apps.paiements.api import PaiementsViewSet
from apps.paiements.models import FactureFrais, PaiementFrais
from apps.paiements.serializers import PaiementCreateSerializer
from apps.paiements.services import PaymentConfirmationRejected, PaymentProviderUnavailable, confirm_card_payment
from django.conf import settings
from django.test import SimpleTestCase
from django.urls import resolve
from rest_framework.exceptions import ValidationError


class PaiementsAPITestCase(SimpleTestCase):
    def test_finance_history_routes_are_registered(self):
        invoice_history = resolve("/api/v1/paiements/factures/1/historique/")
        payment_history = resolve("/api/v1/paiements/transactions/1/historique/")

        assert invoice_history.url_name == "facture-historique"
        assert payment_history.url_name == "paiement-historique"

    def test_student_cannot_submit_payment_for_another_student(self):
        user = SimpleNamespace(
            id=1,
            is_authenticated=True,
            is_superuser=False,
            is_staff=False,
            role="etudiant",
            has_perm=lambda permission: False,
        )
        invoice = SimpleNamespace(
            statut="emise",
            montant=Decimal("100"),
            montant_paye=Decimal("0"),
            etudiant=SimpleNamespace(user_id=2),
        )
        serializer = PaiementCreateSerializer(context={"request": SimpleNamespace(user=user)})

        with self.assertRaisesMessage(ValidationError, "Vous ne pouvez pas payer cette facture"):
            serializer.validate({"facture": invoice, "montant": Decimal("10")})


class CardConfirmationTests(SimpleTestCase):
    def setUp(self):
        self.tenant = SimpleNamespace(pk=7, schema_name="school_a")
        self.facture = SimpleNamespace(
            id=5,
            numero="FAC-5",
            montant=Decimal("100.00"),
            montant_paye=Decimal("0.00"),
            statut="emise",
            etudiant=SimpleNamespace(user=None),
            etudiant_id=3,
            save=Mock(),
        )
        self.paiement = SimpleNamespace(
            pk=12,
            id=12,
            numero="PAY-12",
            facture_id=5,
            montant=Decimal("25.00"),
            mode="carte",
            statut="en_attente",
            reference_externe="pi_ABC123",
            save=Mock(),
        )
        self.intent = {
            "id": self.paiement.reference_externe,
            "status": "succeeded",
            "livemode": True,
            "currency": "eur",
            "amount": 2500,
            "amount_received": 2500,
            "latest_charge": {
                "paid": True,
                "captured": True,
                "disputed": False,
                "refunded": False,
                "amount_refunded": 0,
                "payment_method_details": {"type": "card"},
            },
            "metadata": {
                "sis_variant": settings.SIS_VARIANT,
                "sis_tenant_id": "7",
                "sis_tenant_schema": "school_a",
                "sis_invoice": "FAC-5",
            },
        }

    def test_stripe_confirmation_checks_provider_and_tenant_invoice_amount(self):
        with patch.dict("os.environ", {"SIS_STRIPE_SECRET_KEY": "sk_test_only"}):
            with patch("apps.paiements.services.requests.get") as get:
                get.return_value = Mock(status_code=200, json=Mock(return_value=self.intent))
                confirm_card_payment(self.paiement, self.facture, self.tenant)
                get.assert_called_once_with(
                    "https://api.stripe.com/v1/payment_intents/pi_ABC123",
                    auth=("sk_test_only", ""),
                    params={"expand[]": "latest_charge"},
                    timeout=(3, 8),
                )
                for field, value in (
                    ("status", "processing"),
                    ("livemode", False),
                    ("amount_received", 100),
                    ("currency", "usd"),
                ):
                    with self.subTest(field=field):
                        get.return_value.json.return_value = {**self.intent, field: value}
                        with self.assertRaises(PaymentConfirmationRejected):
                            confirm_card_payment(self.paiement, self.facture, self.tenant)
                get.return_value.json.return_value = self.intent
                for charge_change in (
                    {"refunded": True},
                    {"disputed": True},
                    {"amount_refunded": 100},
                    {"paid": False},
                ):
                    with self.subTest(charge_change=charge_change):
                        get.return_value.json.return_value = {
                            **self.intent,
                            "latest_charge": {**self.intent["latest_charge"], **charge_change},
                        }
                        with self.assertRaises(PaymentConfirmationRejected):
                            confirm_card_payment(self.paiement, self.facture, self.tenant)
                get.return_value.json.return_value = self.intent
                for tenant in (
                    SimpleNamespace(pk=8, schema_name="school_a"),
                    SimpleNamespace(pk=7, schema_name="school_b"),
                ):
                    with self.subTest(tenant=tenant):
                        with self.assertRaises(PaymentConfirmationRejected):
                            confirm_card_payment(self.paiement, self.facture, tenant)
                with self.assertRaises(PaymentConfirmationRejected):
                    confirm_card_payment(self.paiement, SimpleNamespace(numero="FAC-OTHER"), self.tenant)

    def test_missing_credentials_or_invalid_reference_fails_closed(self):
        with patch.dict("os.environ", {"SIS_STRIPE_SECRET_KEY": ""}):
            with self.assertRaises(PaymentProviderUnavailable):
                confirm_card_payment(self.paiement, self.facture, self.tenant)
        self.paiement.reference_externe = "pi_ABC123_secret_fake"
        with patch("apps.paiements.services.requests.get") as get:
            with self.assertRaises(PaymentConfirmationRejected):
                confirm_card_payment(self.paiement, self.facture, self.tenant)
            get.assert_not_called()

    def _approve(self, *, reused=False, confirmed=True):
        request = SimpleNamespace(tenant=self.tenant, user=SimpleNamespace(id=1))
        view = PaiementsViewSet()
        view.request = request
        view.get_object = Mock(return_value=self.paiement)
        view._workflow_for_facture = Mock(return_value={})
        with (
            patch("apps.paiements.api.transaction.atomic", return_value=nullcontext()),
            patch.object(PaiementFrais, "objects") as payments,
            patch.object(FactureFrais, "objects") as factures,
            patch("apps.paiements.api.workflow_transition_allowed", return_value=True),
            patch("apps.paiements.api.record_workflow_event") as event,
            patch(
                "apps.paiements.api.PaiementFraisSerializer",
                return_value=SimpleNamespace(data={"statut": "valide"}),
            ),
            patch("apps.paiements.api.confirm_card_payment") as confirm,
        ):
            payments.select_for_update.return_value.get.return_value = self.paiement
            payments.filter.return_value.exclude.return_value.exists.return_value = reused
            factures.select_for_update.return_value.get.return_value = self.facture
            if not confirmed:
                confirm.side_effect = PaymentConfirmationRejected
            response = view.valider(request, self.paiement.pk)
            if response.status_code == 200:
                repeated = view.valider(request, self.paiement.pk)
                self.assertEqual(repeated.status_code, 409)
                if self.paiement.mode == "carte":
                    confirm.assert_called_once_with(self.paiement, self.facture, self.tenant)
                else:
                    confirm.assert_not_called()
                event.assert_called_once()
            else:
                if reused:
                    confirm.assert_not_called()
                else:
                    confirm.assert_called_once()
                event.assert_not_called()
        return response

    def test_paid_card_credits_once_and_replay_is_idempotent(self):
        response = self._approve()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.facture.montant_paye, Decimal("25.00"))
        self.assertEqual(self.paiement.statut, "valide")
        self.facture.save.assert_called_once()

    def test_reused_or_unconfirmed_card_never_credits_invoice(self):
        for reused in (True, False):
            with self.subTest(reused=reused):
                response = self._approve(reused=reused, confirmed=False)
                self.assertEqual(response.status_code, 409)
                self.assertEqual(self.facture.montant_paye, Decimal("0.00"))
                self.assertEqual(self.paiement.statut, "en_attente")
                self.facture.save.assert_not_called()

    def test_manual_cash_validation_remains_available(self):
        self.paiement.mode = "especes"
        self.paiement.reference_externe = ""
        response = self._approve()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.facture.montant_paye, Decimal("25.00"))
