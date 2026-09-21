"""API views for paiements (ViewSets DRF) - SIS Secondaire."""

import uuid
from pathlib import Path

from django.db import transaction
from django.db.models import Count, Sum
from django.http import FileResponse
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from sis_common.academic_configuration import resolve_financial_workflow, workflow_transition_allowed
from sis_common.authorization import has_business_permission_or_role, user_has_any_role
from sis_common.reporting import configured_report, export_queryset

from .models import Facture, Paiement, TypeFrais
from .serializers import (
    FactureDetailSerializer,
    FactureListSerializer,
    PaiementCreateSerializer,
    PaiementSerializer,
    TypeFraisSerializer,
)

INVOICE_REPORT_FIELDS = {
    "numero": ("Numéro facture", "numero"),
    "eleve": ("Élève", "eleve__user__last_name"),
    "matricule": ("Matricule", "eleve__matricule"),
    "rubrique": ("Rubrique", "type_frais__libelle"),
    "annee": ("Année", "type_frais__annee_scolaire__libelle"),
    "statut": ("Statut", "statut"),
    "montant": ("Montant", "montant"),
    "montant_paye": ("Montant payé", "montant_paye"),
    "date_emission": ("Date émission", "date_emission"),
    "date_echeance": ("Date échéance", "date_echeance"),
}
INVOICE_REPORT_FILTERS = {
    "annee": "type_frais__annee_scolaire_id",
    "rubrique": "type_frais_id",
    "eleve": "eleve_id",
    "statut": "statut",
}
INVOICE_REPORT_GROUPS = {
    "annee": "type_frais__annee_scolaire__libelle",
    "rubrique": "type_frais__libelle",
    "statut": "statut",
}

PAYMENT_REPORT_FIELDS = {
    "numero": ("Numéro paiement", "numero"),
    "facture": ("Numéro facture", "facture__numero"),
    "eleve": ("Élève", "facture__eleve__user__last_name"),
    "matricule": ("Matricule", "facture__eleve__matricule"),
    "rubrique": ("Rubrique", "facture__type_frais__libelle"),
    "annee": ("Année", "facture__type_frais__annee_scolaire__libelle"),
    "mode": ("Mode", "mode"),
    "statut": ("Statut", "statut"),
    "montant": ("Montant", "montant"),
    "date_paiement": ("Date paiement", "date_paiement"),
    "reference_externe": ("Référence externe", "reference_externe"),
}
PAYMENT_REPORT_FILTERS = {
    "annee": "facture__type_frais__annee_scolaire_id",
    "rubrique": "facture__type_frais_id",
    "facture": "facture_id",
    "mode": "mode",
    "statut": "statut",
}
PAYMENT_REPORT_GROUPS = {
    "annee": "facture__type_frais__annee_scolaire__libelle",
    "rubrique": "facture__type_frais__libelle",
    "mode": "mode",
    "statut": "statut",
}


class IsIntendanceOrReadOnly(IsAuthenticated):
    """Permission: intendance/comptabilité pour écriture."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        user = request.user
        model_name = getattr(view, "permission_model", "facture")
        action_name = {
            "create": "add",
            "destroy": "delete",
        }.get(view.action, "change")
        return has_business_permission_or_role(
            user,
            f"paiements.{action_name}_{model_name}",
            (
                "direction",
                "responsable_pedagogique",
                "comptable",
                "personnel_administratif",
            ),
            configuration=getattr(request.tenant, "configuration_academique", {}),
            tenant_group_codes=("finance_manager_secondary",),
        )


class IsFinanceManager(IsAuthenticated):
    def has_permission(self, request, view):
        return super().has_permission(request, view) and has_business_permission_or_role(
            request.user,
            "paiements.change_paiement",
            (
                "direction",
                "responsable_pedagogique",
                "comptable",
                "personnel_administratif",
            ),
            configuration=getattr(request.tenant, "configuration_academique", {}),
            tenant_group_codes=("finance_manager_secondary",),
        )


class TypesFraisViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour types de frais."""

    permission_classes = [IsIntendanceOrReadOnly]
    permission_model = "typefrais"
    serializer_class = TypeFraisSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["annee_scolaire", "periodicite", "obligatoire", "actif"]
    search_fields = ["code", "libelle"]
    ordering = ["libelle"]

    def get_queryset(self):
        return TypeFrais.objects.select_related("annee_scolaire").prefetch_related("factures")


class FacturesViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour factures."""

    permission_classes = [IsIntendanceOrReadOnly]
    permission_model = "facture"
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["eleve", "type_frais", "statut", "type_frais__annee_scolaire"]
    search_fields = ["numero", "eleve__user__last_name", "eleve__matricule"]
    ordering = ["-date_emission"]

    def get_queryset(self):
        queryset = Facture.objects.select_related("eleve__user", "type_frais").prefetch_related("paiements")
        user = self.request.user
        if IsFinanceManager().has_permission(self.request, self):
            return queryset
        if user_has_any_role(user, ("eleve",)):
            return queryset.filter(eleve__user=user)
        if user_has_any_role(user, ("parent",)):
            return queryset.filter(
                eleve__tuteurs_lies__tuteur__user=user,
                eleve__tuteurs_lies__autorise_acces_portail=True,
            ).distinct()
        return queryset.none()

    def get_serializer_class(self):
        if self.action == "list":
            return FactureListSerializer
        return FactureDetailSerializer

    def perform_create(self, serializer):
        numero = f"FAC-{timezone.now().strftime('%Y%m')}-{uuid.uuid4().hex[:6].upper()}"
        serializer.save(numero=numero)

    @action(detail=False, methods=["get"])
    def en_retard(self, request):
        """Liste les factures en retard."""
        today = timezone.now().date()
        factures = self.get_queryset().filter(date_echeance__lt=today, statut__in=["emise", "partielle"])
        serializer = FactureListSerializer(factures, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def annuler(self, request, pk=None):
        """Annule une facture."""
        facture = self.get_object()
        if facture.statut == "payee":
            return Response({"error": "Facture déjà payée."}, status=400)
        facture.statut = "annulee"
        facture.save(update_fields=["statut"])
        return Response({"detail": "Facture annulée.", "id": facture.id})

    @action(detail=False, methods=["get"])
    def statistiques(self, request):
        """Statistiques des factures."""
        qs = self.get_queryset()
        annee = request.query_params.get("annee")
        if annee:
            qs = qs.filter(type_frais__annee_scolaire_id=annee)

        total = qs.aggregate(montant_total=Sum("montant"), montant_paye=Sum("montant_paye"))
        return Response(
            {
                "nb_factures": qs.count(),
                "montant_total": total["montant_total"] or 0,
                "montant_paye": total["montant_paye"] or 0,
                "montant_restant": (total["montant_total"] or 0) - (total["montant_paye"] or 0),
                "par_statut": dict(qs.values_list("statut").annotate(count=Count("id"))),
            }
        )

    @action(detail=False, methods=["get"])
    def bilan(self, request):
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


class PaiementsViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour paiements."""

    permission_classes = [IsIntendanceOrReadOnly]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["facture", "mode", "statut"]
    ordering = ["-date_paiement"]
    http_method_names = ["get", "post", "head", "options"]

    def get_permissions(self):
        if self.action in (
            "valider",
            "rejeter",
            "rembourser",
            "destroy",
            "update",
            "partial_update",
        ):
            return [IsFinanceManager()]
        return [IsAuthenticated()]

    def get_queryset(self):
        queryset = Paiement.objects.select_related("facture__eleve__user", "enregistre_par", "verifie_par")
        user = self.request.user
        if IsFinanceManager().has_permission(self.request, self):
            return queryset
        if user_has_any_role(user, ("eleve",)):
            return queryset.filter(facture__eleve__user=user)
        if user_has_any_role(user, ("parent",)):
            return queryset.filter(
                facture__eleve__tuteurs_lies__tuteur__user=user,
                facture__eleve__tuteurs_lies__autorise_acces_portail=True,
            ).distinct()
        return queryset.none()

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return PaiementCreateSerializer
        return PaiementSerializer

    def perform_create(self, serializer):
        numero = f"PAY-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        paiement = serializer.save(numero=numero, enregistre_par=self.request.user, statut="en_attente")
        return paiement

    def _workflow_for_facture(self, facture):
        return resolve_financial_workflow(
            getattr(self.request.tenant, "configuration_academique", {}),
            [
                {"scope": "payment_rubric", "context": {"payment_rubric_id": facture.type_frais_id}},
                {"scope": "academic_year", "context": {"academic_year_id": facture.type_frais.annee_scolaire_id}},
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
    def valider(self, request, pk=None):
        with transaction.atomic():
            paiement = Paiement.objects.select_for_update().get(pk=self.get_object().pk)
            facture = Facture.objects.select_for_update().get(pk=paiement.facture_id)
            workflow = self._workflow_for_facture(facture)
            if paiement.statut != "en_attente":
                return Response({"error": "Ce paiement a déjà été traité."}, status=409)
            if not workflow_transition_allowed(workflow, "valider", paiement.statut, "valide"):
                return Response({"error": "Transition non autorisée par le workflow financier."}, status=409)
            reste = facture.montant - facture.montant_paye
            if paiement.montant > reste:
                return Response({"error": "Le paiement dépasse le solde de la facture."}, status=409)
            paiement.statut = "valide"
            paiement.verifie_par = request.user
            paiement.verifie_le = timezone.now()
            paiement.motif_rejet = ""
            paiement.save(update_fields=["statut", "verifie_par", "verifie_le", "motif_rejet"])
            facture.montant_paye += paiement.montant
            facture.statut = "payee" if facture.montant_paye >= facture.montant else "partielle"
            facture.save(update_fields=["montant_paye", "statut", "updated_at"])
        return Response(PaiementSerializer(paiement).data)

    @action(detail=True, methods=["post"], permission_classes=[IsFinanceManager])
    def rembourser(self, request, pk=None):
        with transaction.atomic():
            paiement = Paiement.objects.select_for_update().get(pk=self.get_object().pk)
            if paiement.statut != "valide":
                return Response({"error": "Ce paiement ne peut pas être remboursé."}, status=409)
            facture = Facture.objects.select_for_update().get(pk=paiement.facture_id)
            workflow = self._workflow_for_facture(facture)
            if not workflow_transition_allowed(workflow, "rembourser", paiement.statut, "rembourse"):
                return Response({"error": "Transition non autorisée par le workflow financier."}, status=409)
            paiement.statut = "rembourse"
            paiement.verifie_par = request.user
            paiement.verifie_le = timezone.now()
            paiement.save(update_fields=["statut", "verifie_par", "verifie_le"])
            facture.montant_paye = max(facture.montant_paye - paiement.montant, 0)
            facture.statut = "emise" if facture.montant_paye <= 0 else "partielle"
            facture.save(update_fields=["montant_paye", "statut", "updated_at"])
        return Response(PaiementSerializer(paiement).data)

    @action(detail=True, methods=["post"], permission_classes=[IsFinanceManager])
    def rejeter(self, request, pk=None):
        motif = str(request.data.get("motif", "")).strip()
        if not motif:
            return Response({"motif": "Le motif est obligatoire."}, status=400)
        with transaction.atomic():
            paiement = Paiement.objects.select_for_update().get(pk=self.get_object().pk)
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
        return Response(PaiementSerializer(paiement).data)

    @action(detail=False, methods=["get"])
    def bilan(self, request):
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
