"""API views for paiements (ViewSets DRF) - SIS Supérieur."""

import uuid

from django.db.models import Sum
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

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
        return user.is_staff or getattr(user, "role", "") in (
            "comptabilite",
            "scolarite",
            "directeur_etudes",
            "doyen",
        )


class TypesFraisViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour types de frais."""

    permission_classes = [IsComptabiliteOrReadOnly]
    serializer_class = TypeFraisInscriptionSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["annee_universitaire", "periodicite", "obligatoire", "actif"]
    search_fields = ["code", "libelle"]

    def get_queryset(self):
        return TypeFraisInscription.objects.select_related("annee_universitaire")


class FacturesViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour factures."""

    permission_classes = [IsComptabiliteOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["etudiant", "type_frais", "statut"]
    search_fields = ["numero", "etudiant__matricule", "etudiant__user__last_name"]
    ordering_fields = ["date_emission", "date_echeance", "montant"]
    ordering = ["-date_emission"]

    def get_queryset(self):
        qs = FactureFrais.objects.select_related("etudiant__user", "type_frais")
        user = self.request.user
        # Un étudiant ne voit que ses propres factures
        if hasattr(user, "etudiant_profile"):
            if not user.is_staff:
                qs = qs.filter(etudiant__user=user)
        return qs

    def get_serializer_class(self):
        if self.action == "list":
            return FactureFraisListSerializer
        return FactureFraisDetailSerializer

    def perform_create(self, serializer):
        # Générer un numéro de facture unique
        numero = (
            f"FACT-{timezone.now().strftime('%Y%m')}-{uuid.uuid4().hex[:6].upper()}"
        )
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
        qs = self.get_queryset().filter(
            date_echeance__lt=today, statut__in=["emise", "partielle"]
        )
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

    def get_queryset(self):
        return PaiementFrais.objects.select_related(
            "facture__etudiant__user", "enregistre_par"
        )

    def get_serializer_class(self):
        if self.action == "create":
            return PaiementCreateSerializer
        return PaiementFraisSerializer

    def perform_create(self, serializer):
        # Générer un numéro de paiement unique
        numero = (
            f"PAY-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        )
        enregistre_par = (
            self.request.user if self.request.user.is_authenticated else None
        )
        paiement = serializer.save(numero=numero, enregistre_par=enregistre_par)

        # Mettre à jour la facture
        facture = paiement.facture
        facture.montant_paye += paiement.montant
        if facture.montant_paye >= facture.montant:
            facture.statut = "payee"
        else:
            facture.statut = "partielle"
        facture.save(update_fields=["montant_paye", "statut", "updated_at"])

    @action(detail=True, methods=["post"])
    def rembourser(self, request, pk=None):
        """Rembourse un paiement."""
        paiement = self.get_object()
        if paiement.statut != "valide":
            return Response(
                {"error": "Ce paiement ne peut pas être remboursé."}, status=400
            )

        paiement.statut = "rembourse"
        paiement.save(update_fields=["statut"])

        # Mettre à jour la facture
        facture = paiement.facture
        facture.montant_paye -= paiement.montant
        if facture.montant_paye <= 0:
            facture.statut = "emise"
        else:
            facture.statut = "partielle"
        facture.save(update_fields=["montant_paye", "statut", "updated_at"])

        return Response({"detail": "Paiement remboursé.", "id": paiement.id})
