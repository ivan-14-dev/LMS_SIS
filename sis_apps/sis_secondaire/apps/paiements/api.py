"""API views for paiements (ViewSets DRF) - SIS Secondaire."""

import uuid

from django.db.models import Count, Sum
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Facture, Paiement, TypeFrais
from .serializers import (
    FactureDetailSerializer,
    FactureListSerializer,
    PaiementCreateSerializer,
    PaiementSerializer,
    TypeFraisSerializer,
)


class IsIntendanceOrReadOnly(IsAuthenticated):
    """Permission: intendance/comptabilité pour écriture."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        user = request.user
        return user.is_staff or getattr(user, "role", "") in (
            "intendance",
            "comptable",
            "directeur",
            "proviseur",
            "principal",
        )


class TypesFraisViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour types de frais."""

    permission_classes = [IsIntendanceOrReadOnly]
    serializer_class = TypeFraisSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["annee_scolaire", "periodicite", "obligatoire", "actif"]
    search_fields = ["code", "libelle"]
    ordering = ["libelle"]

    def get_queryset(self):
        return TypeFrais.objects.select_related("annee_scolaire").prefetch_related(
            "factures"
        )


class FacturesViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour factures."""

    permission_classes = [IsIntendanceOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["eleve", "type_frais", "statut", "type_frais__annee_scolaire"]
    search_fields = ["numero", "eleve__user__last_name", "eleve__matricule"]
    ordering = ["-date_emission"]

    def get_queryset(self):
        return Facture.objects.select_related(
            "eleve__user", "type_frais"
        ).prefetch_related("paiements")

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
        factures = self.get_queryset().filter(
            date_echeance__lt=today, statut__in=["emise", "partielle"]
        )
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

        total = qs.aggregate(
            montant_total=Sum("montant"), montant_paye=Sum("montant_paye")
        )
        return Response(
            {
                "nb_factures": qs.count(),
                "montant_total": total["montant_total"] or 0,
                "montant_paye": total["montant_paye"] or 0,
                "montant_restant": (total["montant_total"] or 0)
                - (total["montant_paye"] or 0),
                "par_statut": dict(
                    qs.values_list("statut").annotate(count=Count("id"))
                ),
            }
        )


class PaiementsViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour paiements."""

    permission_classes = [IsIntendanceOrReadOnly]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["facture", "mode", "statut"]
    ordering = ["-date_paiement"]

    def get_queryset(self):
        return Paiement.objects.select_related("facture__eleve__user", "enregistre_par")

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return PaiementCreateSerializer
        return PaiementSerializer

    def perform_create(self, serializer):
        numero = (
            f"PAY-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        )
        paiement = serializer.save(
            numero=numero, enregistre_par=self.request.user, statut="valide"
        )
        # Mettre à jour la facture
        facture = paiement.facture
        facture.montant_paye += paiement.montant
        if facture.montant_paye >= facture.montant:
            facture.statut = "payee"
        else:
            facture.statut = "partielle"
        facture.save(update_fields=["montant_paye", "statut"])
