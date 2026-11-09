"""Tenant-local payment review actions. No action initiates a provider transfer."""

from decimal import Decimal

from apps.paiements.services import (
    CURRENCY_EXPONENTS,
    PaymentConfirmationRejected,
    PaymentProviderUnavailable,
    provider_status,
    verify_callback,
)
from django.conf import settings
from django.db import transaction
from django.db.models import Sum
from django.http import FileResponse
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from sis_common.exam_files import validate_payment_proof
from sis_common.workflow_tracking import record_workflow_event


class RefundRequestSerializer(serializers.Serializer):
    motif = serializers.CharField(max_length=1000)
    reference = serializers.CharField(max_length=200)
    preuve = serializers.FileField(validators=[validate_payment_proof])


def confirmed_total(invoice):
    return invoice.paiements.filter(statut="valide").aggregate(total=Sum("montant"))["total"] or Decimal("0")


def reporting_currency(queryset, field="devise"):
    currencies = list(queryset.order_by().values_list(field, flat=True).distinct()[:2])
    if len(currencies) > 1 or (currencies and currencies[0] not in CURRENCY_EXPONENTS):
        raise serializers.ValidationError(
            {"devise": "Devises mélangées ou non configurées : filtrez explicitement par devise."}
        )
    return currencies[0] if currencies else None


def learner(invoice):
    return getattr(invoice, "etudiant", None) or invoice.eleve


def audit(request, payment, action_name, title):
    student = learner(payment.facture)
    user = getattr(student, "user", None)
    tenant_id = getattr(getattr(request, "tenant", None), "pk", None)
    recipients = [user] if user and user.is_active and user.etablissement_id == tenant_id else []
    return record_workflow_event(
        request, payment, action_name, title,
        message=f"{title} : {payment.numero}, facture {payment.facture.numero}.",
        recipients=recipients,
        metadata={"paiement_id": payment.pk, "facture_id": payment.facture_id,
                  "devise": payment.facture.devise, "montant": str(payment.montant)},
    )


class PaymentReviewMixin:
    @action(detail=False, methods=["get"])
    def prestataires(self, request):
        return Response(provider_status())

    @action(detail=True, methods=["get"])
    def recu(self, request, pk=None):
        payment = self.get_object()
        if payment.statut not in ("valide", "rembourse"):
            return Response({"error": "Aucun reçu avant confirmation serveur."}, status=409)
        total = confirmed_total(payment.facture)
        return Response({
            "numero": payment.numero, "facture": payment.facture.numero,
            "montant": payment.montant, "devise": payment.facture.devise,
            "statut": payment.statut, "reference": payment.reference_externe,
            "confirme_le": payment.verifie_le,
            "montant_confirme_facture": total, "solde": payment.facture.montant - total,
            "remboursement": payment.remboursement,
        })

    @action(detail=True, methods=["get"], url_path="justificatif-remboursement")
    def justificatif_remboursement(self, request, pk=None):
        payment = self.get_object()
        if not payment.preuve_remboursement:
            return Response({"error": "Aucun justificatif."}, status=404)
        return FileResponse(payment.preuve_remboursement.open("rb"), as_attachment=True)

    @action(detail=True, methods=["post"], url_path="demander-remboursement")
    @transaction.atomic
    def demander_remboursement(self, request, pk=None):
        payment = self.get_queryset().select_for_update(of=("self",)).get(pk=self.get_object().pk)
        if payment.statut != "valide" or payment.remboursement:
            return Response({"error": "Remboursement déjà demandé ou paiement non confirmé."}, status=409)
        serializer = RefundRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payment.remboursement = {
            "demande_par": request.user.pk, "demande_le": timezone.now().isoformat(),
            "motif": serializer.validated_data["motif"],
            "reference": serializer.validated_data["reference"],
        }
        payment.preuve_remboursement = serializer.validated_data["preuve"]
        payment.save(update_fields=["remboursement", "preuve_remboursement"])
        audit(request, payment, "demande_remboursement", "Remboursement soumis au contrôle distinct")
        return Response(self.get_serializer(payment).data)

    @action(detail=False, methods=["post"], url_path="callback-stripe",
            authentication_classes=[], permission_classes=[AllowAny])
    @transaction.atomic
    def callback_stripe(self, request):
        try:
            event = verify_callback(request.body, request.headers.get("Stripe-Signature", ""))
        except PaymentProviderUnavailable:
            return Response({"error": "Callback Stripe non configuré."}, status=503)
        except PaymentConfirmationRejected:
            return Response({"error": "Signature invalide ou expirée."}, status=403)
        if event.get("type") not in ("payment_intent.succeeded", "payment_intent.payment_failed"):
            return Response({"detail": "Événement non pris en charge."}, status=400)
        data = event.get("data")
        intent = data.get("object") if isinstance(data, dict) else None
        if not isinstance(intent, dict):
            return Response({"error": "Événement invalide."}, status=400)
        metadata = intent.get("metadata") or {}
        tenant = getattr(request, "tenant", None)
        if not isinstance(metadata, dict) or not tenant or (
            metadata.get("sis_variant") != settings.SIS_VARIANT
            or metadata.get("sis_tenant_id") != str(tenant.pk)
            or metadata.get("sis_tenant_schema") != tenant.schema_name
        ):
            return Response({"error": "Événement hors établissement."}, status=403)
        # The model manager is used only after signature and tenant verification;
        # public callbacks cannot inherit a browser user's invoice scope.
        model = self.serializer_class.Meta.model
        candidates = list(model.objects.select_related("facture").filter(
            mode="carte", reference_externe=intent.get("id"), facture__numero=metadata.get("sis_invoice"),
        )[:2])
        if len(candidates) != 1:
            return Response({"error": "Paiement absent ou référence ambiguë."}, status=409)
        payment = candidates[0]
        student = learner(payment.facture)
        year = getattr(payment.facture.type_frais, "annee_universitaire", None) or payment.facture.type_frais.annee_scolaire
        if (
            (getattr(student, "universite_id", None) or getattr(student, "etablissement_id", None)) != tenant.pk
            or (getattr(year, "universite_id", None) or getattr(year, "etablissement_id", None)) != tenant.pk
        ):
            return Response({"error": "Facture hors établissement."}, status=403)
        currency = payment.facture.devise
        if currency not in CURRENCY_EXPONENTS or (
            intent.get("currency") != currency.lower()
            or type(intent.get("amount")) is not int
            or intent["amount"] != payment.montant * Decimal(10) ** CURRENCY_EXPONENTS[currency]
        ):
            return Response({"error": "Montant ou devise incohérent."}, status=409)
        self._provider_callback = True
        self._provider_event_id = event["id"]
        self.get_object = lambda: payment
        if event["type"] == "payment_intent.succeeded":
            return self.valider(request, payment.pk)
        payment = model.objects.select_for_update().get(pk=payment.pk)
        if payment.statut in ("valide", "rembourse", "rejete", "echec"):
            return Response({"detail": "Événement déjà traité ou dépassé."})
        payment.statut = "echec"
        payment.motif_rejet = "Le prestataire signale un échec. Aucun encaissement confirmé."
        payment.save(update_fields=["statut", "motif_rejet"])
        audit(request, payment, "echec_prestataire", "Paiement refusé par le prestataire")
        return Response({"statut": payment.statut})
