"""API views for paiements (ViewSets DRF) - SIS Supérieur."""

import uuid
from pathlib import Path

from django.db import transaction
from django.db.models import Sum
from django.http import FileResponse
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from sis_common.authorization import has_business_permission_or_role

from .models import FactureFrais, PaiementFrais, TypeFraisInscription
from .serializers import (
    FactureFraisDetailSerializer,
    FactureFraisListSerializer,
    PaiementCreateSerializer,
    PaiementFraisSerializer,
    TypeFraisInscriptionSerializer,
)


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
        )


class IsFinanceManager(IsAuthenticated):
    def has_permission(self, request, view):
        return super().has_permission(request, view) and has_business_permission_or_role(
            request.user,
            "paiements.change_paiementfrais",
            ("president", "vice_president", "doyen", "scolarite", "comptable"),
        )


class TypesFraisViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour types de frais."""

    permission_classes = [IsComptabiliteOrReadOnly]
    permission_model = "typefraisinscription"
    serializer_class = TypeFraisInscriptionSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["annee_universitaire", "periodicite", "obligatoire", "actif"]
    search_fields = ["code", "libelle"]

    def get_queryset(self):
        return TypeFraisInscription.objects.select_related("annee_universitaire")


class FacturesViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour factures."""

    permission_classes = [IsComptabiliteOrReadOnly]
    permission_model = "facturefrais"
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["etudiant", "type_frais", "statut"]
    search_fields = ["numero", "etudiant__matricule", "etudiant__user__last_name"]
    ordering_fields = ["date_emission", "date_echeance", "montant"]
    ordering = ["-date_emission"]

    def get_queryset(self):
        qs = FactureFrais.objects.select_related("etudiant__user", "type_frais")
        user = self.request.user
        if IsFinanceManager().has_permission(self.request, self):
            return qs
        if hasattr(user, "etudiant_profile"):
            return qs.filter(etudiant__user=user)
        return qs.none()

    def get_serializer_class(self):
        if self.action == "list":
            return FactureFraisListSerializer
        return FactureFraisDetailSerializer

    def perform_create(self, serializer):
        # Générer un numéro de facture unique
        numero = f"FACT-{timezone.now().strftime('%Y%m')}-{uuid.uuid4().hex[:6].upper()}"
        serializer.save(numero=numero)

    @action(detail=True, methods=["get"])
    def paiements(self, request, pk=None):
        """Liste les paiements de la facture."""
        facture = self.get_object()
        paiements = facture.paiements.filter(statut="valide").order_by("date_paiement")
        serializer = PaiementFraisSerializer(paiements, many=True)
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
        qs = self.get_queryset()
        stats = {
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


class PaiementsViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour paiements."""

    permission_classes = [IsComptabiliteOrReadOnly]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["facture", "mode", "statut"]
    ordering_fields = ["date_paiement", "montant"]
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
        queryset = PaiementFrais.objects.select_related("facture__etudiant__user", "enregistre_par", "verifie_par")
        user = self.request.user
        if IsFinanceManager().has_permission(self.request, self):
            return queryset
        if hasattr(user, "etudiant_profile") and not user.is_staff:
            return queryset.filter(facture__etudiant__user=user)
        return queryset.none()

    def get_serializer_class(self):
        if self.action == "create":
            return PaiementCreateSerializer
        return PaiementFraisSerializer

    def perform_create(self, serializer):
        # Générer un numéro de paiement unique
        numero = f"PAY-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        enregistre_par = self.request.user if self.request.user.is_authenticated else None
        return serializer.save(numero=numero, enregistre_par=enregistre_par, statut="en_attente")

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
            paiement = PaiementFrais.objects.select_for_update().get(pk=self.get_object().pk)
            facture = FactureFrais.objects.select_for_update().get(pk=paiement.facture_id)
            if paiement.statut != "en_attente":
                return Response({"error": "Ce paiement a déjà été traité."}, status=409)
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
        return Response(PaiementFraisSerializer(paiement).data)

    @action(detail=True, methods=["post"], permission_classes=[IsFinanceManager])
    def rejeter(self, request, pk=None):
        motif = str(request.data.get("motif", "")).strip()
        if not motif:
            return Response({"motif": "Le motif est obligatoire."}, status=400)
        with transaction.atomic():
            paiement = PaiementFrais.objects.select_for_update().get(pk=self.get_object().pk)
            if paiement.statut != "en_attente":
                return Response({"error": "Ce paiement a déjà été traité."}, status=409)
            paiement.statut = "rejete"
            paiement.verifie_par = request.user
            paiement.verifie_le = timezone.now()
            paiement.motif_rejet = motif
            paiement.save(update_fields=["statut", "verifie_par", "verifie_le", "motif_rejet"])
        return Response(PaiementFraisSerializer(paiement).data)

    @action(detail=True, methods=["post"])
    def rembourser(self, request, pk=None):
        """Rembourse un paiement."""
        with transaction.atomic():
            paiement = PaiementFrais.objects.select_for_update().get(pk=self.get_object().pk)
            if paiement.statut != "valide":
                return Response({"error": "Ce paiement ne peut pas être remboursé."}, status=400)
            facture = FactureFrais.objects.select_for_update().get(pk=paiement.facture_id)
            paiement.statut = "rembourse"
            paiement.save(update_fields=["statut"])
            facture.montant_paye = max(facture.montant_paye - paiement.montant, 0)
            facture.statut = "emise" if facture.montant_paye <= 0 else "partielle"
            facture.save(update_fields=["montant_paye", "statut", "updated_at"])

        return Response({"detail": "Paiement remboursé.", "id": paiement.id})
