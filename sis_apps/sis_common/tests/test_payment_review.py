"""Run against each SIS variant; all provider traffic and file writes are intercepted."""

import hashlib
import hmac
import json
import time
from decimal import Decimal
from unittest.mock import patch

from apps.core.models import WorkflowEvent, WorkflowNotification
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from django.apps import apps
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone


class PaymentReviewTests(TenantAPITestCase):
    def setUp(self):
        superior = settings.SIS_VARIANT == "superieur"
        self.Payment = apps.get_model("paiements", "PaiementFrais" if superior else "Paiement")
        Invoice = apps.get_model("paiements", "FactureFrais" if superior else "Facture")
        Fee = apps.get_model("paiements", "TypeFraisInscription" if superior else "TypeFrais")
        User = apps.get_model("utilisateurs", "Utilisateur")
        Student = apps.get_model("etudiants" if superior else "eleves", "Etudiant" if superior else "Eleve")
        Year = apps.get_model("etablissement", "AnneeUniversitaire" if superior else "AnneeScolaire")
        self.author = User.objects.create_user("finance-author", role="comptable", etablissement=self.tenant)
        self.reviewer = User.objects.create_user("finance-reviewer", role="comptable", etablissement=self.tenant)
        self.student_user = User.objects.create_user(
            "finance-student", role="etudiant" if superior else "eleve", etablissement=self.tenant,
        )
        tenant_field = "universite" if superior else "etablissement"
        today = timezone.localdate()
        student = Student.objects.create(
            **{tenant_field: self.tenant, "user": self.student_user, "matricule": "FIN-REVIEW",
               "date_naissance": today, "lieu_naissance": "Test", "sexe": "F",
               **({} if superior else {"date_inscription": today})},
        )
        year = Year.objects.create(
            **{tenant_field: self.tenant}, libelle="Finance test", date_debut=today, date_fin=today,
        )
        fee = Fee.objects.create(
            **{"annee_universitaire" if superior else "annee_scolaire": year},
            code="FIN-REVIEW", libelle="Frais de test", montant="100",
        )
        self.invoice = Invoice.objects.create(
            **{"etudiant" if superior else "eleve": student}, type_frais=fee,
            numero="FIN-INV", montant="100", devise="EUR", date_emission=today, date_echeance=today,
        )
        self.payment = self.Payment.objects.create(
            facture=self.invoice, numero="FIN-PAY", montant="25", mode="virement",
            reference_externe="TEST-BANK-1", date_paiement=today, enregistre_par=self.author,
            preuve_paiement="private/test.pdf",
        )
        self.detail = f"/api/v1/paiements/transactions/{self.payment.pk}/"
        self.client.force_authenticate(self.reviewer)

    def test_partial_payment_receipt_and_distinct_refund_reconcile(self):
        assert self.client.get(f"{self.detail}recu/").status_code == 409
        response = self.client.post(f"{self.detail}valider/")
        assert response.status_code == 200, response.data
        self.invoice.refresh_from_db()
        assert self.invoice.montant_paye == Decimal("25")
        assert self.invoice.statut == "partielle"
        assert self.client.get(f"{self.detail}recu/").data["solde"] == Decimal("75")
        assert self.client.post(f"{self.detail}valider/").status_code == 409
        assert WorkflowEvent.objects.filter(action="validation", object_id=str(self.payment.pk)).count() == 1
        assert WorkflowNotification.objects.filter(recipient=self.student_user, category="validation").count() == 1
        self.client.force_authenticate(self.author)
        storage = self.Payment._meta.get_field("preuve_remboursement").storage
        with patch.object(storage, "save", return_value="private/refund.pdf"):
            response = self.client.post(f"{self.detail}demander-remboursement/", {
                "motif": "Remboursement intégral documenté",
                "reference": "TEST-REFUND-1",
                "preuve": SimpleUploadedFile("refund.pdf", b"%PDF-1.4\nproof", content_type="application/pdf"),
            }, format="multipart")
        assert response.status_code == 200, response.data
        assert self.client.post(f"{self.detail}rembourser/").status_code == 403
        self.client.force_authenticate(self.reviewer)
        response = self.client.post(f"{self.detail}rembourser/")
        assert response.status_code == 200, response.data
        assert self.client.post(f"{self.detail}rembourser/").status_code == 200
        self.invoice.refresh_from_db()
        self.payment.refresh_from_db()
        assert self.invoice.montant_paye == Decimal("0")
        assert self.invoice.statut == "emise"
        assert self.payment.verifie_par_id == self.reviewer.pk
        assert WorkflowEvent.objects.filter(action="remboursement", object_id=str(self.payment.pk)).count() == 1
        assert self.client.get(f"{self.detail}recu/").data["statut"] == "rembourse"

    def test_self_review_missing_currency_and_unconfigured_mode_fail_closed(self):
        self.client.force_authenticate(self.author)
        assert self.client.post(f"{self.detail}valider/").status_code == 403
        self.client.force_authenticate(self.reviewer)
        self.invoice.devise = ""
        self.invoice.save(update_fields=["devise"])
        assert self.client.post(f"{self.detail}valider/").status_code == 409
        self.invoice.devise = "EUR"
        self.invoice.save(update_fields=["devise"])
        self.payment.mode = "mobile_money"
        self.payment.save(update_fields=["mode"])
        assert self.client.post(f"{self.detail}valider/").status_code == 503
        self.invoice.refresh_from_db()
        assert self.invoice.montant_paye == 0

    def test_fractional_zero_decimal_currency_is_never_credited(self):
        self.invoice.devise = "XOF"
        self.invoice.save(update_fields=["devise"])
        self.payment.montant = Decimal("25.50")
        self.payment.save(update_fields=["montant"])
        assert self.client.post(f"{self.detail}valider/").status_code == 409
        self.payment.refresh_from_db()
        assert self.payment.statut == "en_attente"

    def test_overpayment_uses_ledger_not_stale_cache(self):
        self.Payment.objects.create(
            facture=self.invoice, numero="FIN-EXIST", montant="90", mode="especes",
            statut="valide", date_paiement=timezone.localdate(),
        )
        assert self.client.post(f"{self.detail}valider/").status_code == 409
        self.payment.refresh_from_db()
        assert self.payment.statut == "en_attente"

    def test_confirmed_reference_cannot_credit_another_payment(self):
        assert self.client.post(f"{self.detail}valider/").status_code == 200
        duplicate = self.Payment.objects.create(
            facture=self.invoice, numero="FIN-DUPLICATE", montant="10", mode="virement",
            reference_externe=self.payment.reference_externe, date_paiement=timezone.localdate(),
            enregistre_par=self.author, preuve_paiement="private/test.pdf",
        )
        response = self.client.post(f"/api/v1/paiements/transactions/{duplicate.pk}/valider/")
        assert response.status_code == 409, response.data
        self.invoice.refresh_from_db()
        assert self.invoice.montant_paye == Decimal("25")

    def test_reporting_refuses_mixed_currencies_and_excludes_cancelled_debt(self):
        other = type(self.invoice).objects.get(pk=self.invoice.pk)
        other.pk = None
        other.numero = "FIN-USD"
        other.devise = "USD"
        other.save()
        url = "/api/v1/paiements/factures/statistiques/"
        assert self.client.get(url).status_code == 400
        scoped = self.client.get(f"{url}?devise=EUR")
        assert scoped.status_code == 200, scoped.data
        assert scoped.data["devise"] == "EUR"
        other.statut = "annulee"
        other.save(update_fields=["statut"])
        assert self.client.get(url).status_code == 200

    def test_audit_failure_rolls_back_confirmation_and_notification(self):
        with patch("apps.paiements.api.record_workflow_event", side_effect=RuntimeError("audit unavailable")):
            try:
                self.client.post(f"{self.detail}valider/")
            except RuntimeError:
                pass
            else:
                raise AssertionError("Audit failure was swallowed")
        self.payment.refresh_from_db()
        self.invoice.refresh_from_db()
        assert self.payment.statut == "en_attente"
        assert self.invoice.montant_paye == 0

    def test_invoice_is_immutable_after_declaration_and_cannot_be_deleted(self):
        detail = f"/api/v1/paiements/factures/{self.invoice.pk}/"
        assert self.client.patch(detail, {"montant": "200"}, format="json").status_code == 400
        assert self.client.patch(detail, {"devise": "USD"}, format="json").status_code == 400
        assert self.client.delete(detail).status_code == 405

    def callback(self, *, event_type="payment_intent.succeeded", tenant_id=None, amount=2500, signed=True):
        intent = {
            "id": "pi_TEST1", "amount": amount, "currency": "eur",
            "metadata": {
                "sis_variant": settings.SIS_VARIANT, "sis_tenant_id": str(tenant_id or self.tenant.pk),
                "sis_tenant_schema": self.tenant.schema_name, "sis_invoice": self.invoice.numero,
            },
        }
        body = json.dumps({"id": "evt_TEST1", "type": event_type, "data": {"object": intent}}).encode()
        timestamp = str(int(time.time()))
        digest = hmac.new(b"only-test-secret", timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()
        signature = f"t={timestamp},v1={digest}" if signed else "invalid"
        self.client.force_authenticate(None)
        with patch.dict("os.environ", {"SIS_STRIPE_WEBHOOK_SECRET": "only-test-secret"}):
            return self.client.post(
                "/api/v1/paiements/transactions/callback-stripe/", body,
                content_type="application/json", HTTP_STRIPE_SIGNATURE=signature,
            )

    def test_signed_callback_replay_failure_and_recovery(self):
        self.payment.mode = "carte"
        self.payment.reference_externe = "pi_TEST1"
        self.payment.save(update_fields=["mode", "reference_externe"])
        assert self.callback(signed=False).status_code == 403
        assert self.callback(tenant_id=999999).status_code == 403
        assert self.callback(amount=999).status_code == 409
        assert self.callback(event_type="payment_intent.payment_failed").status_code == 200
        assert self.callback(event_type="payment_intent.payment_failed").status_code == 200
        self.payment.refresh_from_db()
        assert self.payment.statut == "echec"
        assert WorkflowEvent.objects.filter(action="echec_prestataire").count() == 1
        with patch("apps.paiements.api.confirm_card_payment") as provider:
            response = self.callback()
            assert response.status_code == 200, response.data
            assert self.callback().status_code == 200
            provider.assert_called_once()
        self.invoice.refresh_from_db()
        assert self.invoice.montant_paye == Decimal("25")
        assert WorkflowEvent.objects.filter(action="validation", object_id=str(self.payment.pk)).count() == 1

    def test_browser_cannot_confirm_without_provider_and_receipt_stays_unavailable(self):
        self.payment.mode = "carte"
        self.payment.reference_externe = "pi_TEST1"
        self.payment.save(update_fields=["mode", "reference_externe"])
        with patch.dict("os.environ", {"SIS_STRIPE_SECRET_KEY": ""}):
            assert self.client.post(f"{self.detail}valider/").status_code == 503
        assert self.client.patch(self.detail, {"statut": "valide"}).status_code == 405
        assert self.client.get(f"{self.detail}recu/").status_code == 409
