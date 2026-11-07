"""API tests for paiements."""

from contextlib import nullcontext
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch

from apps.eleves.models import Eleve
from apps.etablissement.models import AnneeScolaire
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.paiements.api import FacturesViewSet, IsFinanceManager, PaiementsViewSet
from apps.paiements.models import Facture, Paiement, TypeFrais
from apps.paiements.serializers import PaiementCreateSerializer
from apps.paiements.services import PaymentConfirmationRejected, PaymentProviderUnavailable, confirm_card_payment
from apps.utilisateurs.models import Utilisateur
from django.conf import settings
from django.test import SimpleTestCase
from django.urls import resolve
from django_tenants.utils import schema_context
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIRequestFactory, force_authenticate


class EmptyGuardianLinks:
    def filter(self, **kwargs):
        return self

    def exists(self):
        return False


class PaiementsAPITestCase(SimpleTestCase):
    def test_finance_history_routes_are_registered(self):
        invoice_history = resolve("/api/v1/paiements/factures/1/historique/")
        payment_history = resolve("/api/v1/paiements/transactions/1/historique/")

        assert invoice_history.url_name == "facture-historique"
        assert payment_history.url_name == "paiement-historique"

    def test_user_cannot_submit_payment_for_another_pupil(self):
        user = SimpleNamespace(
            id=1,
            is_authenticated=True,
            is_superuser=False,
            is_staff=False,
            role="parent",
            has_perm=lambda permission: False,
        )
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


class ConfirmedInvoiceBalanceTests(SimpleTestCase):
    def test_balance_counts_only_validated_payments_and_shows_overpayment(self):
        invoice = SimpleNamespace(montant=Decimal("100.00"), montant_paye=Decimal("99.00"), save=Mock())
        view = FacturesViewSet()
        view.get_object = Mock(return_value=invoice)
        cases = (
            ([], "0.00", "100.00"),
            ([("valide", "30.00"), ("valide", "20.00"), ("en_attente", "90.00"),
              ("echec", "90.00"), ("rejete", "90.00"), ("rembourse", "90.00")], "50.00", "50.00"),
            ([("valide", "100.00"), ("rembourse", "20.00")], "100.00", "0.00"),
            ([("valide", "120.00"), ("echec", "50.00")], "120.00", "-20.00"),
            ([("rembourse", "100.00")], "0.00", "100.00"),
        )
        for rows, expected_total, expected_balance in cases:
            with self.subTest(rows=rows), patch.object(Paiement, "objects") as payments:
                # The fake aggregate uses the status filter supplied by the view, not the cached invoice total.
                def aggregate_for(**filters):
                    return SimpleNamespace(
                        aggregate=lambda **kwargs: {
                            "total": sum(
                                (Decimal(amount) for status, amount in rows if status == filters["statut"]),
                                Decimal("0.00"),
                            ) if rows else None,
                        },
                    )

                payments.filter.side_effect = aggregate_for
                response = view.solde_confirme(SimpleNamespace())
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.data, {
                    "montant_facture": Decimal("100.00"),
                    "total_paiements_confirmes": Decimal(expected_total),
                    "solde_confirme": Decimal(expected_balance),
                })
                payments.filter.assert_called_once_with(facture=invoice, statut="valide")
                self.assertEqual(invoice.montant_paye, Decimal("99.00"))
                invoice.save.assert_not_called()

    def test_balance_route_is_read_only(self):
        route = resolve("/api/v1/paiements/factures/5/solde-confirme/")
        self.assertEqual(route.url_name, "facture-solde-confirme")
        self.assertEqual(route.func.actions, {"get": "solde_confirme", "head": "solde_confirme"})

    def test_balance_http_denies_other_tenants_and_unrelated_roles(self):
        path = "/api/v1/paiements/factures/5/solde-confirme/"
        endpoint = resolve(path).func
        tenant = SimpleNamespace(pk=7, configuration_academique={})
        with patch.object(FacturesViewSet, "get_throttles", return_value=[]):
            for role, etablissement_id in (("comptable", 8), ("enseignant", 7)):
                with self.subTest(role=role, etablissement_id=etablissement_id):
                    request = APIRequestFactory().get(path)
                    request.tenant = tenant
                    user = SimpleNamespace(
                        id=1, pk=1, role=role, etablissement_id=etablissement_id,
                        is_authenticated=True, is_active=True, is_superuser=False, has_perm=lambda permission: False,
                    )
                    force_authenticate(request, user=user)
                    self.assertEqual(endpoint(request, pk="5").status_code, 404)

    def test_balance_queryset_restricts_tenant_and_role(self):
        view = FacturesViewSet()
        view.action = "solde_confirme"
        manager = SimpleNamespace(
            id=1, etablissement_id=7, role="comptable", is_authenticated=True,
            is_active=True, is_superuser=False, has_perm=lambda permission: False,
        )
        view.request = SimpleNamespace(user=manager, tenant=SimpleNamespace(pk=7, configuration_academique={}))
        with patch.object(Facture, "objects") as invoices:
            queryset = invoices.select_related.return_value.prefetch_related.return_value
            queryset.filter.return_value = queryset
            queryset.distinct.return_value = queryset
            self.assertIs(view.get_queryset(), queryset)
            queryset.filter.assert_any_call(
                eleve__etablissement_id=7, type_frais__annee_scolaire__etablissement_id=7,
            )
            queryset.filter.assert_any_call(pk__in=queryset.order_by.return_value.values.return_value)

            for tenant, user_id in ((SimpleNamespace(pk=8, configuration_academique={}), 7),
                                    (SimpleNamespace(pk=7, configuration_academique={}), 8),
                                    (None, 7)):
                with self.subTest(tenant=tenant, user_id=user_id):
                    manager.etablissement_id = user_id
                    view.request.tenant = tenant
                    queryset.reset_mock()
                    self.assertIs(view.get_queryset(), queryset.none.return_value)
                    queryset.filter.assert_not_called()
            manager.etablissement_id = 7
            view.request.tenant = SimpleNamespace(pk=7, configuration_academique={})
            manager.role = "eleve"
            queryset.reset_mock()
            self.assertIs(view.get_queryset(), queryset)
            self.assertEqual(queryset.filter.call_count, 3)
            queryset.filter.assert_any_call(eleve__user=manager)
            manager.role = "parent"
            queryset.reset_mock()
            self.assertIs(view.get_queryset(), queryset.distinct.return_value)
            queryset.filter.assert_any_call(
                eleve__tuteurs_lies__tuteur__user=manager,
                eleve__tuteurs_lies__autorise_acces_portail=True,
            )
            manager.role = "enseignant"
            queryset.reset_mock()
            self.assertIs(view.get_queryset(), queryset.none.return_value)


class InvoiceCancellationTests(TenantAPITestCase):
    def setUp(self):
        manager = Utilisateur.objects.create_user(
            "invoice-cancellation-manager", role="comptable", etablissement=self.tenant
        )
        self.client.force_authenticate(manager)
        student = Utilisateur.objects.create_user(
            "invoice-cancellation-student", role="eleve", etablissement=self.tenant
        )
        self.eleve = Eleve.objects.create(
            etablissement=self.tenant, user=student, matricule="REFUND-1",
            date_naissance="2010-01-01", lieu_naissance="Paris", sexe="F",
            date_inscription="2026-09-01",
        )
        year = AnneeScolaire.objects.create(
            etablissement=self.tenant, libelle="2026-2027",
            date_debut="2026-09-01", date_fin="2027-08-31",
        )
        self.fee = TypeFrais.objects.create(
            annee_scolaire=year, code="TUITION", libelle="Scolarité", montant="100.00",
        )
        self.facture = Facture.objects.create(
            eleve=self.eleve, type_frais=self.fee, numero="FAC-REFUND-1",
            date_emission="2026-09-01", date_echeance="2026-10-01", montant="100.00",
        )
        self.url = f"/api/v1/paiements/factures/{self.facture.pk}/annuler/"

    def test_unpaid_invoice_can_be_cancelled_once_and_replay_does_not_repeat_event(self):
        Paiement.objects.create(
            facture=self.facture, numero="PAY-PENDING-1", date_paiement="2026-09-02",
            montant="25.00", mode="especes", statut="en_attente",
        )
        with patch("apps.paiements.api.record_workflow_event") as event:
            response = self.client.post(self.url)
            assert response.status_code == 200, response.data
            assert self.client.post(self.url).status_code == 409
            event.assert_called_once()
        self.facture.refresh_from_db()
        assert self.facture.statut == "annulee"
        assert self.facture.montant_paye == Decimal("0.00")

    def test_confirmed_payment_blocks_cancellation_even_when_cached_total_is_stale(self):
        Paiement.objects.create(
            facture=self.facture, numero="PAY-CONFIRMED-1", date_paiement="2026-09-02",
            montant="25.00", mode="especes", statut="valide",
        )
        self.facture.statut = "partielle"
        self.facture.save(update_fields=["statut"])
        with patch("apps.paiements.api.record_workflow_event") as event:
            response = self.client.post(self.url)
            assert response.status_code == 409, response.data
            event.assert_not_called()
        self.facture.refresh_from_db()
        assert self.facture.statut == "partielle"
        assert self.facture.montant_paye == Decimal("0.00")

    def test_cancellation_cannot_target_another_school_in_the_same_schema(self):
        foreign = type(self.tenant)(schema_name="foreign_invoice_cancel")
        self.setup_tenant(foreign)
        foreign.auto_create_schema = False
        with schema_context("public"):
            foreign.save()
        foreign_year = AnneeScolaire.objects.create(
            etablissement=foreign, libelle="2026-2027",
            date_debut="2026-09-01", date_fin="2027-08-31",
        )
        foreign_fee = TypeFrais.objects.create(
            annee_scolaire=foreign_year, code="FOREIGN", libelle="Autre", montant="100.00",
        )
        with patch("apps.paiements.api.record_workflow_event") as event:
            for pupil_school, fee in ((foreign, self.fee), (self.tenant, foreign_fee)):
                with self.subTest(pupil_school=pupil_school.pk, fee=fee.pk):
                    self.eleve.etablissement = pupil_school
                    self.eleve.save(update_fields=["etablissement"])
                    self.facture.type_frais = fee
                    self.facture.save(update_fields=["type_frais"])
                    response = self.client.post(self.url)
                    assert response.status_code == 404, response.data
            event.assert_not_called()
        self.facture.refresh_from_db()
        assert self.facture.statut == "emise"


class PaymentSchoolIsolationTests(TenantAPITestCase):
    def setUp(self):
        self.manager = Utilisateur.objects.create_user(
            "payment-school-manager", role="comptable", etablissement=self.tenant
        )
        self.client.force_authenticate(self.manager)
        student = Utilisateur.objects.create_user(
            "payment-school-student", role="eleve", etablissement=self.tenant
        )
        pupil = Eleve.objects.create(
            etablissement=self.tenant, user=student, matricule="PAY-SCHOOL-1",
            date_naissance="2010-01-01", lieu_naissance="Paris", sexe="F",
            date_inscription="2026-09-01",
        )
        year = AnneeScolaire.objects.create(
            etablissement=self.tenant, libelle="2026-2027",
            date_debut="2026-09-01", date_fin="2027-08-31",
        )
        fee = TypeFrais.objects.create(
            annee_scolaire=year, code="PAY-SCHOOL", libelle="Scolarité", montant="100.00",
        )
        self.invoice = Facture.objects.create(
            eleve=pupil, type_frais=fee, numero="FAC-PAY-SCHOOL",
            date_emission="2026-09-01", date_echeance="2026-10-01", montant="100.00",
        )
        self.transactions_url = "/api/v1/paiements/transactions/"

    def submit(self, invoice):
        return self.client.post(self.transactions_url, {
            "facture": invoice.pk,
            "date_paiement": "2026-09-02",
            "montant": "25.00",
            "mode": "especes",
        }, format="json")

    def test_manager_cannot_submit_or_settle_another_schools_invoice(self):
        foreign = type(self.tenant)(schema_name="foreign_payment_scope")
        self.setup_tenant(foreign)
        foreign.auto_create_schema = False
        with schema_context("public"):
            foreign.save()
        foreign_student = Utilisateur.objects.create_user(
            "foreign-payment-student", role="eleve", etablissement=foreign
        )
        foreign_pupil = Eleve.objects.create(
            etablissement=foreign, user=foreign_student, matricule="PAY-SCHOOL-FOREIGN",
            date_naissance="2010-01-01", lieu_naissance="Paris", sexe="F",
            date_inscription="2026-09-01",
        )
        foreign_year = AnneeScolaire.objects.create(
            etablissement=foreign, libelle="2026-2027",
            date_debut="2026-09-01", date_fin="2027-08-31",
        )
        foreign_fee = TypeFrais.objects.create(
            annee_scolaire=foreign_year, code="PAY-FOREIGN", libelle="Autre", montant="100.00",
        )
        foreign_invoice = Facture.objects.create(
            eleve=foreign_pupil, type_frais=foreign_fee, numero="FAC-PAY-FOREIGN",
            date_emission="2026-09-01", date_echeance="2026-10-01", montant="100.00",
        )
        mixed_invoice = Facture.objects.create(
            eleve=self.invoice.eleve, type_frais=foreign_fee, numero="FAC-PAY-MIXED",
            date_emission="2026-09-01", date_echeance="2026-10-01", montant="100.00",
        )
        for invoice in (foreign_invoice, mixed_invoice):
            response = self.submit(invoice)
            assert response.status_code == 400, response.data
            assert not Paiement.objects.filter(facture=invoice).exists()

            pending = Paiement.objects.create(
                facture=invoice, numero=f"PAY-SCHOOL-FOREIGN-{invoice.pk}",
                date_paiement="2026-09-02", montant="25.00", mode="especes", statut="en_attente",
            )
            detail = f"{self.transactions_url}{pending.pk}/"
            assert self.client.get(detail).status_code == 404
            assert self.client.post(f"{detail}valider/").status_code == 404
            assert self.client.post(f"{detail}rejeter/", {"motif": "Autre"}).status_code == 404
            pending.refresh_from_db()
            invoice.refresh_from_db()
            assert pending.statut == "en_attente"
            assert invoice.montant_paye == Decimal("0.00")

        created = self.submit(self.invoice)
        assert created.status_code == 201, created.data
        local_payment = Paiement.objects.get(facture=self.invoice)
        assert local_payment.statut == "en_attente"
        with patch("apps.paiements.api.record_workflow_event"):
            validated = self.client.post(f"{self.transactions_url}{local_payment.pk}/valider/")
        assert validated.status_code == 200, validated.data
        self.invoice.refresh_from_db()
        assert self.invoice.montant_paye == Decimal("25.00")
        assert self.invoice.statut == "partielle"

    def test_manager_from_another_school_cannot_access_local_payments(self):
        created = self.submit(self.invoice)
        assert created.status_code == 201, created.data
        local_payment = Paiement.objects.get(facture=self.invoice)
        foreign = type(self.tenant)(schema_name="foreign_payment_manager")
        self.setup_tenant(foreign)
        foreign.auto_create_schema = False
        with schema_context("public"):
            foreign.save()
        foreign_manager = Utilisateur.objects.create_user(
            "foreign-payment-manager", role="comptable", etablissement=foreign
        )
        self.client.force_authenticate(foreign_manager)
        assert self.submit(self.invoice).status_code == 400
        detail = f"{self.transactions_url}{local_payment.pk}/"
        assert self.client.get(detail).status_code == 404
        assert self.client.post(f"{detail}valider/").status_code == 404
        self.invoice.refresh_from_db()
        assert self.invoice.montant_paye == Decimal("0.00")


class CardConfirmationTests(SimpleTestCase):
    def setUp(self):
        self.tenant = SimpleNamespace(pk=7, schema_name="school_a")
        self.facture = SimpleNamespace(
            id=5,
            numero="FAC-5",
            montant=Decimal("100.00"),
            montant_paye=Decimal("0.00"),
            statut="emise",
            eleve=SimpleNamespace(user=None),
            eleve_id=3,
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
            patch.object(Paiement, "objects") as payments,
            patch.object(Facture, "objects") as factures,
            patch("apps.paiements.api.workflow_transition_allowed", return_value=True),
            patch("apps.paiements.api.record_workflow_event") as event,
            patch("apps.paiements.api.PaiementSerializer", return_value=SimpleNamespace(data={"statut": "valide"})),
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

    def test_pending_cash_payment_cannot_credit_cancelled_invoice(self):
        self.facture.statut = "annulee"
        self.paiement.mode = "especes"
        path = f"/api/v1/paiements/transactions/{self.paiement.pk}/valider/"
        endpoint = resolve(path).func
        request = APIRequestFactory().post(path)
        request.tenant = self.tenant
        force_authenticate(request, user=SimpleNamespace(id=1, pk=1, is_authenticated=True))
        with (
            patch.object(IsFinanceManager, "has_permission", return_value=True),
            patch.object(PaiementsViewSet, "get_object", return_value=self.paiement),
            patch.object(PaiementsViewSet, "get_throttles", return_value=[]),
            patch.object(PaiementsViewSet, "_workflow_for_facture", return_value={}),
            patch("apps.paiements.api.transaction.atomic", return_value=nullcontext()),
            patch.object(Paiement, "objects") as payments,
            patch.object(Facture, "objects") as factures,
            patch("apps.paiements.api.workflow_transition_allowed", return_value=True),
            patch("apps.paiements.api.record_workflow_event") as event,
            patch("apps.paiements.api.PaiementSerializer", return_value=SimpleNamespace(data={})),
        ):
            payments.select_for_update.return_value.get.return_value = self.paiement
            factures.select_for_update.return_value.get.return_value = self.facture
            response = endpoint(request, pk=str(self.paiement.pk))

        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.paiement.statut, "en_attente")
        self.assertEqual(self.facture.statut, "annulee")
        self.assertEqual(self.facture.montant_paye, Decimal("0.00"))
        self.paiement.save.assert_not_called()
        self.facture.save.assert_not_called()
        event.assert_not_called()

    def test_card_cannot_be_accounted_as_refunded_without_provider_refund(self):
        self.paiement.statut = "valide"
        request = SimpleNamespace(tenant=self.tenant, user=SimpleNamespace(id=1))
        view = PaiementsViewSet()
        view.request = request
        view.get_object = Mock(return_value=self.paiement)
        view._workflow_for_facture = Mock(return_value={})
        with (
            patch("apps.paiements.api.transaction.atomic", return_value=nullcontext()),
            patch.object(Paiement, "objects") as payments,
            patch.object(Facture, "objects") as factures,
            patch("apps.paiements.api.workflow_transition_allowed", return_value=True),
            patch("apps.paiements.api.record_workflow_event") as event,
            patch("apps.paiements.api.PaiementSerializer", return_value=SimpleNamespace(data={})),
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
