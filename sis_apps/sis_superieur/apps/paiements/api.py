"""API views for paiements (ViewSets DRF) - SIS Supérieur."""

import uuid
from decimal import Decimal
from pathlib import Path

from apps.core.serializers import WorkflowEventSerializer
from django.db import IntegrityError, transaction
from django.db.models import Count, Sum
from django.http import FileResponse
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from sis_common.academic_configuration import resolve_financial_workflow, workflow_transition_allowed
from sis_common.authorization import filter_queryset_by_scopes, has_business_permission_or_role
from sis_common.payment_review import PaymentReviewMixin, audit, confirmed_total, reporting_currency
from sis_common.reporting import configured_report, export_queryset
from sis_common.workflow_tracking import record_workflow_event, workflow_history_queryset

from .models import FactureFrais, PaiementFrais, TypeFraisInscription
from .serializers import (
    FactureFraisDetailSerializer,
    FactureFraisListSerializer,
    PaiementCreateSerializer,
    PaiementFraisSerializer,
    TypeFraisInscriptionSerializer,
)
from .services import (
    CURRENCY_EXPONENTS,
    MANUAL_MODES,
    PaymentConfirmationRejected,
    PaymentProviderUnavailable,
    confirm_card_payment,
)

INVOICE_REPORT_FIELDS = {
    "devise": ("Devise", "devise"),
    "numero": ("Numéro facture", "numero"),
    "etudiant": ("Étudiant", "etudiant__user__last_name"),
    "matricule": ("Matricule", "etudiant__matricule"),
    "rubrique": ("Rubrique", "type_frais__libelle"),
    "formation": ("Formation", "type_frais__formations__nom"),
    "annee": ("Année", "type_frais__annee_universitaire__libelle"),
    "statut": ("Statut", "statut"),
    "montant": ("Montant", "montant"),
    "montant_paye": ("Montant payé", "montant_paye"),
    "date_emission": ("Date émission", "date_emission"),
    "date_echeance": ("Date échéance", "date_echeance"),
}
INVOICE_REPORT_FILTERS = {
    "annee": "type_frais__annee_universitaire_id",
    "rubrique": "type_frais_id",
    "etudiant": "etudiant_id",
    "statut": "statut",
}
INVOICE_REPORT_GROUPS = {
    "annee": "type_frais__annee_universitaire__libelle",
    "rubrique": "type_frais__libelle",
    "statut": "statut",
}

PAYMENT_REPORT_FIELDS = {
    "devise": ("Devise", "facture__devise"),
    "numero": ("Numéro paiement", "numero"),
    "facture": ("Numéro facture", "facture__numero"),
    "etudiant": ("Étudiant", "facture__etudiant__user__last_name"),
    "matricule": ("Matricule", "facture__etudiant__matricule"),
    "rubrique": ("Rubrique", "facture__type_frais__libelle"),
    "annee": ("Année", "facture__type_frais__annee_universitaire__libelle"),
    "mode": ("Mode", "mode"),
    "statut": ("Statut", "statut"),
    "montant": ("Montant", "montant"),
    "date_paiement": ("Date paiement", "date_paiement"),
    "reference_externe": ("Référence externe", "reference_externe"),
}
PAYMENT_REPORT_FILTERS = {
    "annee": "facture__type_frais__annee_universitaire_id",
    "rubrique": "facture__type_frais_id",
    "facture": "facture_id",
    "mode": "mode",
    "statut": "statut",
}
PAYMENT_REPORT_GROUPS = {
    "annee": "facture__type_frais__annee_universitaire__libelle",
    "rubrique": "facture__type_frais__libelle",
    "mode": "mode",
    "statut": "statut",
}


def _superior_finance_recipients(request, etudiant):
    recipients = []
    tenant_id = getattr(getattr(request, "tenant", None), "pk", None)
    user = getattr(etudiant, "user", None)
    if user is not None and user.is_active and user.etablissement_id == tenant_id:
        recipients.append(user)
    actor = getattr(request, "user", None)
    if (
        getattr(actor, "is_authenticated", False) and actor not in recipients
        and getattr(actor, "etablissement_id", None) == tenant_id
    ):
        recipients.append(actor)
    return recipients


class IsComptabiliteOrReadOnly(IsAuthenticated):
    """Permission: comptabilité pour écriture, authentifié pour lecture."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        user = request.user
        model_name = getattr(view, "permission_model", "facturefrais")
        action_name = {
            "create": "add",
            "destroy": "delete",
        }.get(view.action, "change")
        return has_business_permission_or_role(
            user,
            f"paiements.{action_name}_{model_name}",
            (
                "president",
                "vice_president",
                "doyen",
                "scolarite",
                "comptable",
            ),
            configuration=getattr(request.tenant, "configuration_academique", {}),
            tenant_group_codes=("finance_manager_superieur",),
        )


class IsFinanceManager(IsAuthenticated):
    def has_permission(self, request, view):
        return super().has_permission(request, view) and has_business_permission_or_role(
            request.user,
            "paiements.change_paiementfrais",
            ("president", "vice_president", "doyen", "scolarite", "comptable"),
            configuration=getattr(request.tenant, "configuration_academique", {}),
            tenant_group_codes=("finance_manager_superieur",),
        )


def visible_invoices(request):
    """Share the balance endpoint's tenant/owner policy across invoice reads.

    Invoice read scopes can only narrow access. Scoped finance grants still
    require the existing finance authorization check; they never grant access
    through the legacy-role fallback.
    """
    tenant_id = getattr(getattr(request, "tenant", None), "pk", None)
    user = request.user
    base_queryset = FactureFrais.objects.select_related("etudiant__user", "type_frais")
    queryset = base_queryset.filter(
        etudiant__universite_id=tenant_id,
        type_frais__annee_universitaire__universite_id=tenant_id,
    )
    if (
        tenant_id is None
        or not user.is_authenticated
        or not user.is_active
        or user.etablissement_id != tenant_id
    ):
        return queryset.none()

    scope_fields = {
        "factures": "pk",
        "etudiants": "etudiant_id",
        "rubriques": "type_frais_id",
        "annees": "type_frais__annee_universitaire_id",
    }
    if user.role in ("etudiant", "doctorant"):
        queryset = queryset.filter(etudiant__user_id=user.pk)
    elif user.role == "parent" or not IsFinanceManager().has_permission(request, None):
        return queryset.none()
    else:
        queryset = filter_queryset_by_scopes(
            queryset, user, "paiements.change_paiementfrais", scope_fields
        )
    visible_ids = filter_queryset_by_scopes(
        queryset, user, "paiements.view_facturefrais", scope_fields
    ).order_by().values("pk")
    return base_queryset.filter(pk__in=visible_ids)


class TypesFraisViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour types de frais."""

    permission_classes = [IsComptabiliteOrReadOnly]
    permission_model = "typefraisinscription"
    serializer_class = TypeFraisInscriptionSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["annee_universitaire", "periodicite", "obligatoire", "actif"]
    search_fields = ["code", "libelle"]

    def get_queryset(self):
        return TypeFraisInscription.objects.select_related("annee_universitaire").filter(
            annee_universitaire__universite_id=getattr(getattr(self.request, "tenant", None), "pk", None)
        )


class FacturesViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour factures."""

    permission_classes = [IsComptabiliteOrReadOnly]
    permission_model = "facturefrais"
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["etudiant", "type_frais", "statut"]
    search_fields = ["numero", "etudiant__matricule", "etudiant__user__last_name"]
    ordering_fields = ["date_emission", "date_echeance", "montant"]
    ordering = ["-date_emission"]
    http_method_names = ["get", "post", "patch", "head", "options"]

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        self.get_queryset().select_for_update().get(pk=self.get_object().pk)
        return super().update(request, *args, **kwargs)

    def get_queryset(self):
        queryset = visible_invoices(self.request)
        currency = getattr(self.request, "query_params", {}).get("devise")
        return queryset.filter(devise=currency) if currency else queryset

    def get_serializer_class(self):
        if self.action == "list":
            return FactureFraisListSerializer
        return FactureFraisDetailSerializer

    @transaction.atomic
    def perform_create(self, serializer):
        # Générer un numéro de facture unique
        numero = f"FACT-{timezone.now().strftime('%Y%m')}-{uuid.uuid4().hex[:6].upper()}"
        facture = serializer.save(numero=numero)
        record_workflow_event(
            self.request, facture, "emission", "Facture émise",
            recipients=_superior_finance_recipients(self.request, facture.etudiant),
            metadata={"facture_id": facture.pk, "montant": str(facture.montant), "devise": facture.devise},
        )

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def annuler(self, request, pk=None):
        facture = self.get_queryset().select_for_update().get(pk=self.get_object().pk)
        if facture.statut == "annulee" or facture.paiements.filter(statut="valide").exists():
            return Response({"error": "Facture annulée ou comportant un encaissement confirmé."}, status=409)
        facture.statut = "annulee"
        facture.save(update_fields=["statut", "updated_at"])
        record_workflow_event(
            request, facture, "annulation", "Facture annulée",
            recipients=_superior_finance_recipients(request, facture.etudiant),
            metadata={"facture_id": facture.pk},
        )
        return Response({"detail": "Facture annulée."})

    @action(detail=True, methods=["get"])
    def solde(self, request, pk=None):
        """Calcule le solde à partir des seuls paiements validés encore actifs."""
        facture = self.get_object()
        confirme = (
            facture.paiements.filter(statut="valide").aggregate(total=Sum("montant"))["total"] or Decimal("0.00")
        )
        return Response(
            {
                "facture": facture.pk,
                "montant_facture": facture.montant,
                "montant_confirme": confirme,
                "reste_a_payer": facture.montant - confirme,
            }
        )

    @action(detail=True, methods=["get"])
    def paiements(self, request, pk=None):
        """Liste les paiements de la facture."""
        facture = self.get_object()
        paiements = facture.paiements.filter(statut="valide").order_by("date_paiement")
        serializer = PaiementFraisSerializer(paiements, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def historique(self, request, pk=None):
        """Historique workflow de la facture."""
        facture = self.get_object()
        serializer = WorkflowEventSerializer(workflow_history_queryset(facture), many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def en_retard(self, request):
        """Liste les factures en retard."""
        today = timezone.now().date()
        qs = self.get_queryset().filter(date_echeance__lt=today, statut__in=["emise", "partielle"])
        serializer = FactureFraisListSerializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def statistiques(self, request):
        """Statistiques des factures."""
        qs = self.get_queryset().exclude(statut="annulee")
        currency = reporting_currency(qs)
        stats = {
            "devise": currency,
            "total_emis": qs.aggregate(total=Sum("montant"))["total"] or 0,
            "total_paye": qs.aggregate(total=Sum("montant_paye"))["total"] or 0,
            "nb_factures": qs.count(),
            "nb_payees": qs.filter(statut="payee").count(),
            "nb_en_retard": qs.filter(
                date_echeance__lt=timezone.now().date(),
                statut__in=["emise", "partielle"],
            ).count(),
        }
        stats["reste_a_percevoir"] = stats["total_emis"] - stats["total_paye"]
        return Response(stats)

    @action(detail=False, methods=["get"])
    def bilan(self, request):
        currency = reporting_currency(self.filter_queryset(self.get_queryset()))
        group_by = request.query_params.get("group_by", "rubrique")
        group_field = INVOICE_REPORT_GROUPS.get(group_by)
        if not group_field:
            return Response(
                {"group_by": f"Valeurs acceptées: {', '.join(INVOICE_REPORT_GROUPS)}."},
                status=400,
            )
        rows = (
            self.filter_queryset(self.get_queryset())
            .values(group_field)
            .annotate(nombre=Count("id"), montant_total=Sum("montant"), montant_paye=Sum("montant_paye"))
            .order_by(group_field)
        )
        return Response(
            [
                {
                    "groupe": row[group_field],
                    "devise": currency,
                    "nombre": row["nombre"],
                    "montant_total": row["montant_total"] or 0,
                    "montant_paye": row["montant_paye"] or 0,
                }
                for row in rows
            ]
        )

    @action(detail=False, methods=["post"])
    def exporter(self, request):
        report = configured_report(request, request.data.get("report"), allowed_datasets={"financial_invoices"})
        return export_queryset(
            request,
            self.filter_queryset(self.get_queryset()),
            report,
            INVOICE_REPORT_FIELDS,
            INVOICE_REPORT_FILTERS,
            request.data.get("filters", {}),
        )


class PaiementsViewSet(PaymentReviewMixin, viewsets.ModelViewSet):
    """ViewSet CRUD pour paiements."""

    permission_classes = [IsComptabiliteOrReadOnly]
    serializer_class = PaiementFraisSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["facture", "mode", "statut"]
    ordering_fields = ["date_paiement", "montant"]
    ordering = ["-date_paiement"]
    http_method_names = ["get", "post", "head", "options"]

    def get_permissions(self):
        if self.action == "callback_stripe":
            return [AllowAny()]
        if self.action in (
            "valider",
            "rejeter",
            "rembourser",
            "demander_remboursement",
            "destroy",
            "update",
            "partial_update",
        ):
            return [IsFinanceManager()]
        return [IsAuthenticated()]

    def get_queryset(self):
        queryset = PaiementFrais.objects.select_related("facture__etudiant__user", "enregistre_par", "verifie_par")
        queryset = queryset.filter(facture__in=visible_invoices(self.request))
        currency = getattr(self.request, "query_params", {}).get("devise")
        return queryset.filter(facture__devise=currency) if currency else queryset

    def get_serializer_class(self):
        if self.action == "create":
            return PaiementCreateSerializer
        return PaiementFraisSerializer

    @transaction.atomic
    def perform_create(self, serializer):
        # Générer un numéro de paiement unique
        numero = f"PAY-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        enregistre_par = self.request.user if self.request.user.is_authenticated else None
        invoice = FactureFrais.objects.select_for_update().get(pk=serializer.validated_data["facture"].pk)
        serializer.validated_data["facture"] = invoice
        serializer.validate(serializer.validated_data)
        paiement = serializer.save(numero=numero, enregistre_par=enregistre_par, statut="en_attente")
        audit(self.request, paiement, "soumission", "Paiement en attente de confirmation")
        return paiement

    def _workflow_for_facture(self, facture):
        return resolve_financial_workflow(
            getattr(self.request.tenant, "configuration_academique", {}),
            [
                {"scope": "payment_rubric", "context": {"payment_rubric_id": facture.type_frais_id}},
                {"scope": "academic_year", "context": {"academic_year_id": facture.type_frais.annee_universitaire_id}},
                {"scope": "tenant", "context": {"tenant_id": getattr(self.request.tenant, "id", None)}},
            ],
        )

    @action(detail=True, methods=["get"])
    def justificatif(self, request, pk=None):
        paiement = self.get_object()
        if not paiement.preuve_paiement:
            return Response({"error": "Aucun justificatif."}, status=404)
        return FileResponse(
            paiement.preuve_paiement.open("rb"),
            as_attachment=True,
            filename=(f"justificatif-{paiement.numero}" f"{Path(paiement.preuve_paiement.name).suffix.lower()}"),
        )

    @action(detail=True, methods=["post"], permission_classes=[IsFinanceManager])
    @transaction.atomic
    def valider(self, request, pk=None):
        paiement = None
        try:
            with transaction.atomic():
                paiement = PaiementFrais.objects.select_for_update().get(pk=self.get_object().pk)
                facture = FactureFrais.objects.select_for_update().get(pk=paiement.facture_id)
                workflow = self._workflow_for_facture(facture)
                callback = getattr(self, "_provider_callback", False)
                if callback and paiement.statut in ("valide", "rembourse"):
                    return Response({"detail": "Confirmation déjà comptabilisée."})
                if paiement.statut not in ("en_attente", "echec"):
                    return Response({"error": "Ce paiement a déjà été traité."}, status=409)
                if facture.statut not in ("emise", "partielle", "en_retard"):
                    return Response({"error": "Facture non payable."}, status=409)
                if facture.devise not in CURRENCY_EXPONENTS:
                    return Response({"error": "Devise non configurée."}, status=409)
                if paiement.montant <= 0 or (
                    CURRENCY_EXPONENTS[facture.devise] == 0 and paiement.montant != paiement.montant.to_integral_value()
                ):
                    return Response({"error": "Montant invalide pour cette devise."}, status=409)
                if paiement.mode not in (*MANUAL_MODES, "carte"):
                    return Response({"error": "Prestataire non configuré."}, status=503)
                if not callback and (
                    not paiement.enregistre_par_id or paiement.enregistre_par_id == request.user.pk
                ):
                    return Response({"error": "Un contrôleur distinct du déclarant est obligatoire."}, status=403)
                if paiement.mode in MANUAL_MODES and (
                    not paiement.preuve_paiement or not paiement.reference_externe.strip()
                ):
                    return Response({"error": "Preuve et référence de rapprochement obligatoires."}, status=409)
                if not workflow_transition_allowed(workflow, "valider", "en_attente", "valide"):
                    return Response({"error": "Transition non autorisée par le workflow financier."}, status=409)
                facture.montant_paye = confirmed_total(facture)
                reste = facture.montant - facture.montant_paye
                if paiement.montant > reste:
                    return Response({"error": "Le paiement dépasse le solde de la facture."}, status=409)
                reused = (
                        PaiementFrais.objects.filter(
                            reference_externe=paiement.reference_externe,
                            mode=paiement.mode,
                            statut__in=("valide", "rembourse"),
                        )
                        .exclude(pk=paiement.pk)
                        .exists()
                    )
                if reused:
                    return Response({"error": "Référence de paiement déjà utilisée."}, status=409)
                if paiement.mode == "carte":
                    try:
                        confirm_card_payment(paiement, facture, request.tenant)
                    except PaymentConfirmationRejected:
                        return Response({"error": "Paiement non confirmé pour cette facture."}, status=409)
                    except PaymentProviderUnavailable:
                        return Response({"error": "Prestataire de paiement indisponible."}, status=503)
                paiement.statut = "valide"
                paiement.verifie_par = None if callback else request.user
                paiement.verifie_le = timezone.now()
                paiement.motif_rejet = ""
                paiement.save(update_fields=["statut", "verifie_par", "verifie_le", "motif_rejet"])
                facture.montant_paye += paiement.montant
                facture.statut = "payee" if facture.montant_paye >= facture.montant else "partielle"
                facture.save(update_fields=["montant_paye", "statut", "updated_at"])
        except IntegrityError:
            if paiement is None or not PaiementFrais.objects.filter(
                reference_externe=paiement.reference_externe,
                mode=paiement.mode,
                statut__in=("valide", "rembourse"),
            ).exclude(pk=paiement.pk).exists():
                raise
            return Response({"error": "Référence de carte déjà utilisée."}, status=409)
        record_workflow_event(
            request,
            paiement,
            "validation",
            "Paiement validé",
            message=f"Le paiement {paiement.numero} a été validé pour la facture {facture.numero}.",
            recipients=_superior_finance_recipients(request, facture.etudiant),
            metadata={
                "paiement_id": paiement.id,
                "facture_id": facture.id,
                "etudiant_id": facture.etudiant_id,
                "statut_facture": facture.statut,
                "provider_event_id": getattr(self, "_provider_event_id", ""),
            },
        )
        return Response(PaiementFraisSerializer(paiement).data)

    @action(detail=True, methods=["post"], permission_classes=[IsFinanceManager])
    @transaction.atomic
    def rejeter(self, request, pk=None):
        motif = str(request.data.get("motif", "")).strip()
        if not motif:
            return Response({"motif": "Le motif est obligatoire."}, status=400)
        with transaction.atomic():
            paiement = PaiementFrais.objects.select_for_update().get(pk=self.get_object().pk)
            workflow = self._workflow_for_facture(paiement.facture)
            if paiement.statut != "en_attente":
                return Response({"error": "Ce paiement a déjà été traité."}, status=409)
            if not workflow_transition_allowed(workflow, "rejeter", paiement.statut, "rejete"):
                return Response({"error": "Transition non autorisée par le workflow financier."}, status=409)
            paiement.statut = "rejete"
            paiement.verifie_par = request.user
            paiement.verifie_le = timezone.now()
            paiement.motif_rejet = motif
            paiement.save(update_fields=["statut", "verifie_par", "verifie_le", "motif_rejet"])
        record_workflow_event(
            request,
            paiement,
            "rejet",
            "Paiement rejeté",
            message=f"Le paiement {paiement.numero} a été rejeté pour la facture {paiement.facture.numero}.",
            recipients=_superior_finance_recipients(request, paiement.facture.etudiant),
            metadata={
                "paiement_id": paiement.id,
                "facture_id": paiement.facture_id,
                "etudiant_id": paiement.facture.etudiant_id,
                "motif_rejet": motif,
            },
        )
        return Response(PaiementFraisSerializer(paiement).data)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def rembourser(self, request, pk=None):
        """Rembourse un paiement."""
        with transaction.atomic():
            paiement = PaiementFrais.objects.select_for_update().get(pk=self.get_object().pk)
            if paiement.statut == "rembourse":
                return Response(PaiementFraisSerializer(paiement).data)
            if paiement.statut != "valide":
                return Response({"error": "Ce paiement ne peut pas être remboursé."}, status=400)
            facture = FactureFrais.objects.select_for_update().get(pk=paiement.facture_id)
            if not paiement.remboursement or not paiement.preuve_remboursement:
                return Response({"error": "Demande et justificatif de remboursement obligatoires."}, status=409)
            if paiement.remboursement["demande_par"] == request.user.pk:
                return Response({"error": "Un autre acteur doit contrôler ce remboursement."}, status=403)
            if paiement.mode == "carte":
                try:
                    confirm_card_payment(paiement, facture, request.tenant, refunded=True)
                except PaymentConfirmationRejected:
                    return Response({"error": "Remboursement intégral non confirmé par Stripe."}, status=409)
                except PaymentProviderUnavailable:
                    return Response({"error": "Prestataire non configuré ou indisponible."}, status=503)
            elif paiement.mode not in MANUAL_MODES:
                return Response({"error": "Prestataire non configuré."}, status=503)
            workflow = self._workflow_for_facture(facture)
            if not workflow_transition_allowed(workflow, "rembourser", paiement.statut, "rembourse"):
                return Response({"error": "Transition non autorisée par le workflow financier."}, status=409)
            paiement.statut = "rembourse"
            paiement.remboursement.update({"confirme_par": request.user.pk, "confirme_le": timezone.now().isoformat()})
            paiement.save(update_fields=["statut", "remboursement"])
            facture.montant_paye = confirmed_total(facture)
            facture.statut = "emise" if facture.montant_paye <= 0 else "partielle"
            facture.save(update_fields=["montant_paye", "statut", "updated_at"])
        record_workflow_event(
            request,
            paiement,
            "remboursement",
            "Paiement remboursé",
            message=f"Le paiement {paiement.numero} a été remboursé pour la facture {facture.numero}.",
            recipients=_superior_finance_recipients(request, facture.etudiant),
            metadata={
                "paiement_id": paiement.id,
                "facture_id": facture.id,
                "etudiant_id": facture.etudiant_id,
                "statut_facture": facture.statut,
            },
        )

        return Response({"detail": "Paiement remboursé.", "id": paiement.id})

    @action(detail=True, methods=["get"])
    def historique(self, request, pk=None):
        """Historique workflow du paiement."""
        paiement = self.get_object()
        serializer = WorkflowEventSerializer(workflow_history_queryset(paiement), many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def bilan(self, request):
        currency = reporting_currency(self.filter_queryset(self.get_queryset()), "facture__devise")
        group_by = request.query_params.get("group_by", "statut")
        group_field = PAYMENT_REPORT_GROUPS.get(group_by)
        if not group_field:
            return Response(
                {"group_by": f"Valeurs acceptées: {', '.join(PAYMENT_REPORT_GROUPS)}."},
                status=400,
            )
        rows = (
            self.filter_queryset(self.get_queryset())
            .values(group_field)
            .annotate(nombre=Count("id"), montant_total=Sum("montant"))
            .order_by(group_field)
        )
        return Response(
            [
                {
                    "groupe": row[group_field],
                    "devise": currency,
                    "nombre": row["nombre"],
                    "montant_total": row["montant_total"] or 0,
                }
                for row in rows
            ]
        )

    @action(detail=False, methods=["post"])
    def exporter(self, request):
        report = configured_report(request, request.data.get("report"), allowed_datasets={"financial_payments"})
        return export_queryset(
            request,
            self.filter_queryset(self.get_queryset()),
            report,
            PAYMENT_REPORT_FIELDS,
            PAYMENT_REPORT_FILTERS,
            request.data.get("filters", {}),
        )
