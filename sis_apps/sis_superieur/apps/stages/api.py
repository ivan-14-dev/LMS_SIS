"""API views for stages (ViewSets DRF) - SIS Supérieur."""

from django.db.models import Count
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import CandidatureStage, ConventionStage, OffreStage
from .serializers import (
    CandidatureStageSerializer,
    ConventionStageDetailSerializer,
    ConventionStageListSerializer,
    OffreStageDetailSerializer,
    OffreStageListSerializer,
)


class IsRelationsEntreprisesOrReadOnly(IsAuthenticated):
    """Permission: relations entreprises pour écriture."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        user = request.user
        return user.is_staff or getattr(user, "role", "") in (
            "relations_entreprises",
            "scolarite",
            "responsable_formation",
            "doyen",
        )


class OffresStageViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour offres de stage."""

    permission_classes = [IsRelationsEntreprisesOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["formation", "entreprise", "type", "statut", "pays", "publiee"]
    search_fields = ["titre", "description", "lieu", "entreprise__raison_sociale"]
    ordering_fields = ["date_debut", "date_limite_candidature", "remuneration"]
    ordering = ["-date_limite_candidature"]

    def get_queryset(self):
        qs = OffreStage.objects.select_related("entreprise", "formation")
        user = self.request.user
        # Les étudiants ne voient que les offres publiées et ouvertes
        if hasattr(user, "etudiant_profile"):
            if not user.is_staff:
                qs = qs.filter(publiee=True, statut="ouverte")
        return qs

    def get_serializer_class(self):
        if self.action == "list":
            return OffreStageListSerializer
        return OffreStageDetailSerializer

    @action(detail=True, methods=["get"])
    def candidatures(self, request, pk=None):
        """Liste les candidatures pour l'offre."""
        offre = self.get_object()
        candidatures = offre.candidatures.select_related("etudiant__user").order_by(
            "-date_soumission"
        )
        serializer = CandidatureStageSerializer(candidatures, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def fermer(self, request, pk=None):
        """Ferme l'offre aux nouvelles candidatures."""
        offre = self.get_object()
        if offre.statut != "ouverte":
            return Response({"error": "L'offre n'est pas ouverte."}, status=400)
        offre.statut = "fermee"
        offre.save(update_fields=["statut"])
        return Response({"detail": "Offre fermée.", "id": offre.id})

    @action(detail=False, methods=["get"])
    def statistiques(self, request):
        """Statistiques des offres."""
        qs = self.get_queryset()
        stats = {
            "total": qs.count(),
            "ouvertes": qs.filter(statut="ouverte").count(),
            "pourvues": qs.filter(statut="pourvue").count(),
            "fermees": qs.filter(statut="fermee").count(),
        }
        by_type = qs.values("type").annotate(count=Count("id"))
        stats["par_type"] = {t["type"]: t["count"] for t in by_type}
        return Response(stats)


class CandidaturesStageViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour candidatures."""

    permission_classes = [IsAuthenticated]
    serializer_class = CandidatureStageSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["offre", "etudiant", "statut"]
    ordering = ["-date_soumission"]

    def get_queryset(self):
        qs = CandidatureStage.objects.select_related(
            "etudiant__user", "offre__entreprise"
        )
        user = self.request.user
        # Un étudiant ne voit que ses propres candidatures
        if hasattr(user, "etudiant_profile"):
            if not user.is_staff:
                qs = qs.filter(etudiant__user=user)
        return qs

    def perform_create(self, serializer):
        # L'étudiant connecté est le candidat
        if hasattr(self.request.user, "etudiant_profile"):
            serializer.save(etudiant=self.request.user.etudiant_profile)
        else:
            serializer.save()

    @action(detail=True, methods=["post"])
    def accepter(self, request, pk=None):
        """Accepte la candidature."""
        candidature = self.get_object()
        if candidature.statut in ("acceptee", "refusee"):
            return Response({"error": "La candidature est déjà traitée."}, status=400)
        candidature.statut = "acceptee"
        candidature.date_reponse = timezone.now()
        candidature.save(update_fields=["statut", "date_reponse"])
        return Response({"detail": "Candidature acceptée.", "id": candidature.id})

    @action(detail=True, methods=["post"])
    def refuser(self, request, pk=None):
        """Refuse la candidature."""
        candidature = self.get_object()
        if candidature.statut in ("acceptee", "refusee"):
            return Response({"error": "La candidature est déjà traitée."}, status=400)
        candidature.statut = "refusee"
        candidature.date_reponse = timezone.now()
        candidature.motif_refus = request.data.get("motif", "")
        candidature.save(update_fields=["statut", "date_reponse", "motif_refus"])
        return Response({"detail": "Candidature refusée.", "id": candidature.id})


class ConventionsStageViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour conventions de stage."""

    permission_classes = [IsRelationsEntreprisesOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["etudiant", "entreprise", "statut"]

    def get_queryset(self):
        qs = ConventionStage.objects.select_related(
            "etudiant__user", "entreprise", "offre"
        )
        user = self.request.user
        # Un étudiant ne voit que ses propres conventions
        if hasattr(user, "etudiant_profile"):
            if not user.is_staff:
                qs = qs.filter(etudiant__user=user)
        return qs

    def get_serializer_class(self):
        if self.action == "list":
            return ConventionStageListSerializer
        return ConventionStageDetailSerializer
