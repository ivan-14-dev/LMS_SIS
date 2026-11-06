"""API tests for paiements."""

from contextlib import nullcontext
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch

from apps.etablissement.models import AnneeUniversitaire, Universite
from apps.etudiants.models import Etudiant
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.paiements.api import FacturesViewSet, PaiementsViewSet
from apps.paiements.models import FactureFrais, PaiementFrais, TypeFraisInscription
from apps.paiements.serializers import FactureFraisDetailSerializer, PaiementCreateSerializer
from apps.paiements.services import PaymentConfirmationRejected, PaymentProviderUnavailable, confirm_card_payment
from apps.utilisateurs.models import Utilisateur
from django.conf import settings
from django.db import connection
from django.test import SimpleTestCase
from django.urls import resolve
from django.utils import timezone
from django_tenants.utils import schema_context
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIRequestFactory, force_authenticate


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


class InvoiceStateAPITests(SimpleTestCase):
    def test_patch_cannot_forge_or_reopen_paid_invoice(self):
        for original, attempted, paid in (
            ("emise", "payee", Decimal("0.00")),
            ("payee", "emise", Decimal("100.00")),
        ):
            with self.subTest(original=original, attempted=attempted):
                facture = FactureFrais(statut=original, montant=Decimal("100.00"), montant_paye=paid)
                facture.save = Mock()
                request = APIRequestFactory().patch(
                    "/api/v1/paiements/factures/5/", {"statut": attempted, "note": "Correction"}, format="json"
                )
                force_authenticate(request, user=SimpleNamespace(pk=1, is_authenticated=True))
                with (
                    patch("apps.paiements.api.IsComptabiliteOrReadOnly.has_permission", return_value=True),
                    patch.object(FacturesViewSet, "get_throttles", return_value=[]),
                    patch.object(FacturesViewSet, "get_object", return_value=facture),
                    patch.object(
                        FactureFraisDetailSerializer,
                        "to_representation",
                        side_effect=lambda obj: {"statut": obj.statut, "montant_paye": obj.montant_paye},
                    ),
                ):
                    response = FacturesViewSet.as_view({"patch": "partial_update"})(request, pk=5)

                self.assertEqual(response.status_code, 200)
                self.assertEqual(facture.statut, original)
                self.assertEqual(response.data["statut"], original)
                self.assertEqual(facture.montant_paye, paid)
                self.assertEqual(facture.note, "Correction")

    def test_patch_cannot_change_invoice_amount_after_payment(self):
        route = resolve("/api/v1/paiements/factures/5/")
        self.assertEqual(route.url_name, "facture-detail")
        for statut, paid in (("payee", Decimal("100.00")), ("partielle", Decimal("25.00"))):
            with self.subTest(statut=statut):
                facture = FactureFrais(statut=statut, montant=Decimal("100.00"), montant_paye=paid)
                facture.save = Mock()
                request = APIRequestFactory().patch(
                    "/api/v1/paiements/factures/5/", {"montant": "150.00"}, format="json"
                )
                force_authenticate(request, user=SimpleNamespace(pk=1, is_authenticated=True))
                with (
                    patch("apps.paiements.api.IsComptabiliteOrReadOnly.has_permission", return_value=True),
                    patch.object(FacturesViewSet, "get_throttles", return_value=[]),
                    patch.object(FacturesViewSet, "get_object", return_value=facture),
                    patch.object(
                        FactureFraisDetailSerializer,
                        "to_representation",
                        side_effect=lambda obj: {"montant": obj.montant, "statut": obj.statut},
                    ),
                ):
                    response = route.func(request, pk=5)

                self.assertEqual(response.status_code, 400)
                self.assertIn("montant", response.data)
                self.assertEqual(facture.montant, Decimal("100.00"))
                facture.save.assert_not_called()


class ConfirmedInvoiceBalanceTests(TenantAPITestCase):
    def setUp(self):
        today = timezone.localdate()
        self.student_user = Utilisateur.objects.create_user(
            "balance-student", role="etudiant", etablissement=self.tenant
        )
        self.student = Etudiant.objects.create(
            universite=self.tenant,
            user=self.student_user,
            matricule="BAL-1",
            date_naissance=today,
            lieu_naissance="Test",
            sexe="F",
        )
        self.year = AnneeUniversitaire.objects.create(
            universite=self.tenant,
            libelle="balance-year",
            date_debut=today,
            date_fin=today,
        )
        self.rubric = TypeFraisInscription.objects.create(
            annee_universitaire=self.year, code="BAL", libelle="Frais de test", montant=Decimal("100.00")
        )
        self.invoice = self._invoice(self.student, self.rubric, "BAL-INV-1")
        self.manager = Utilisateur.objects.create_user("balance-manager", role="comptable", etablissement=self.tenant)
        self.url = f"/api/v1/paiements/factures/{self.invoice.pk}/solde/"

    def _invoice(self, student, rubric, numero):
        today = timezone.localdate()
        return FactureFrais.objects.create(
            etudiant=student,
            type_frais=rubric,
            numero=numero,
            date_emission=today,
            date_echeance=today,
            montant=Decimal("100.00"),
        )

    def _payment(self, numero, amount, status, *, mode="especes"):
        return PaiementFrais.objects.create(
            facture=self.invoice,
            numero=numero,
            date_paiement=timezone.localdate(),
            montant=Decimal(amount),
            mode=mode,
            statut=status,
        )

    def test_validated_payment_produces_server_derived_full_balance(self):
        self._payment("BAL-PAY-1", "100.00", "valide")
        self.client.force_authenticate(self.student_user)
        self.assertEqual(resolve(self.url).url_name, "facture-solde")

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["montant_facture"], Decimal("100.00"))
        self.assertEqual(response.data["montant_confirme"], Decimal("100.00"))
        self.assertEqual(response.data["reste_a_payer"], Decimal("0.00"))
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.montant_paye, Decimal("0.00"))

    def test_partial_balance_excludes_pending_card_and_refunded_payment(self):
        self._payment("BAL-PAY-2", "25.00", "valide")
        self._payment("BAL-PAY-3", "50.00", "en_attente", mode="carte")
        self._payment("BAL-PAY-4", "25.00", "rembourse")
        self.client.force_authenticate(self.manager)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["montant_confirme"], Decimal("25.00"))
        self.assertEqual(response.data["reste_a_payer"], Decimal("75.00"))

    def test_unrelated_student_parent_and_foreign_university_are_denied(self):
        other_user = Utilisateur.objects.create_user("balance-other", role="etudiant", etablissement=self.tenant)
        parent = Utilisateur.objects.create_user("balance-parent", role="parent", etablissement=self.tenant)
        parent.is_superuser = True
        parent.save(update_fields=["is_superuser"])
        foreign = Universite(schema_name="foreign_balance")
        self.setup_tenant(foreign)
        foreign.auto_create_schema = False
        with schema_context("public"):
            foreign.save()
        foreign_manager = Utilisateur.objects.create_user(
            "balance-foreign-manager", role="comptable", etablissement=foreign
        )
        foreign_year = AnneeUniversitaire.objects.create(
            universite=foreign, libelle="foreign-balance", date_debut=timezone.localdate(),
            date_fin=timezone.localdate(),
        )
        foreign_rubric = TypeFraisInscription.objects.create(
            annee_universitaire=foreign_year, code="FOREIGN", libelle="Frais étrangers", montant=Decimal("100.00")
        )
        foreign_invoice = self._invoice(self.student, foreign_rubric, "BAL-FOREIGN-1")
        foreign_student_user = Utilisateur.objects.create_user(
            "balance-foreign-student", role="etudiant", etablissement=foreign
        )
        foreign_student = Etudiant.objects.create(
            universite=foreign,
            user=foreign_student_user,
            matricule="BAL-FOREIGN",
            date_naissance=timezone.localdate(),
            lieu_naissance="Test",
            sexe="F",
        )
        foreign_student_invoice = self._invoice(foreign_student, self.rubric, "BAL-FOREIGN-2")
        for actor, url in (
            (other_user, self.url),
            (parent, self.url),
            (foreign_manager, self.url),
            (self.manager, f"/api/v1/paiements/factures/{foreign_invoice.pk}/solde/"),
            (self.student_user, f"/api/v1/paiements/factures/{foreign_invoice.pk}/solde/"),
            (self.manager, f"/api/v1/paiements/factures/{foreign_student_invoice.pk}/solde/"),
            (foreign_student_user, f"/api/v1/paiements/factures/{foreign_student_invoice.pk}/solde/"),
        ):
            with self.subTest(actor=actor.username, url=url):
                self.client.force_authenticate(actor)
                response = self.client.get(url)
                self.assertEqual(response.status_code, 404, response.data)
        self.assertEqual(connection.schema_name, self.tenant.schema_name)

    def test_repeated_balance_reads_never_credit_or_create_payments(self):
        pending = self._payment("BAL-PAY-5", "100.00", "en_attente", mode="carte")
        self.client.force_authenticate(self.student_user)

        first = self.client.get(self.url)
        second = self.client.get(self.url)

        self.assertEqual(first.status_code, 200, first.data)
        self.assertEqual(second.data, first.data)
        self.assertEqual(second.data["montant_confirme"], Decimal("0.00"))
        self.assertEqual(PaiementFrais.objects.filter(facture=self.invoice).count(), 1)
        pending.refresh_from_db()
        self.invoice.refresh_from_db()
        self.assertEqual(pending.statut, "en_attente")
        self.assertEqual(self.invoice.montant_paye, Decimal("0.00"))


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

    def test_card_cannot_be_accounted_as_refunded_without_provider_refund(self):
        self.paiement.statut = "valide"
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
        ):
            payments.select_for_update.return_value.get.return_value = self.paiement
            factures.select_for_update.return_value.get.return_value = self.facture
            self.facture.montant_paye = Decimal("25.00")
            response = view.rembourser(request, self.paiement.pk)
            self.assertEqual(response.status_code, 409)
            self.assertEqual(self.paiement.statut, "valide")
            self.assertEqual(self.facture.montant_paye, Decimal("25.00"))
            self.paiement.save.assert_not_called()
            self.facture.save.assert_not_called()
            event.assert_not_called()
            self.paiement.mode = "especes"
            response = view.rembourser(request, self.paiement.pk)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(self.paiement.statut, "rembourse")
            self.assertEqual(self.facture.montant_paye, Decimal("0.00"))
            self.facture.save.assert_called_once()
            event.assert_called_once()
