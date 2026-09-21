"""API views for memoires (ViewSets DRF) - SIS Supérieur."""

from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from sis_common.authorization import request_has_business_access

from .models import JuryMemoire, Memoire, SujetMemoire
from .serializers import (
    JuryMemoireSerializer,
    MemoireDetailSerializer,
    MemoireListSerializer,
    SujetMemoireDetailSerializer,
    SujetMemoireListSerializer,
)


class IsEnseignantOrScolarite(IsAuthenticated):
    """Permission: enseignant ou scolarité pour écriture."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        return (
            request_has_business_access(
                request,
                "memoires.change_memoire",
                ("scolarite", "responsable_formation"),
                tenant_group_codes=("memoire_manager_superieur",),
            )
            or hasattr(request.user, "personnel_profile")
        )


class SujetsMemoireViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour sujets de mémoire."""

    permission_classes = [IsEnseignantOrScolarite]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["formation", "annee_universitaire", "statut", "encadreur"]
    search_fields = ["titre", "description", "mots_cles"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return SujetMemoire.objects.select_related(
            "formation", "encadreur__user", "co_encadreur__user", "laboratoire"
        ).prefetch_related("memoires")

    def get_serializer_class(self):
        if self.action == "list":
            return SujetMemoireListSerializer
        return SujetMemoireDetailSerializer

    @action(detail=False, methods=["get"])
    def disponibles(self, request):
        """Liste les sujets disponibles (non attribués)."""
        sujets = self.get_queryset().filter(statut="propose")
        serializer = SujetMemoireListSerializer(sujets, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def publier(self, request, pk=None):
        """Publie le sujet."""
        sujet = self.get_object()
        sujet.date_publication = timezone.now().date()
        sujet.statut = "propose"
        sujet.save(update_fields=["date_publication", "statut"])
        return Response({"detail": "Sujet publié.", "id": sujet.id})


class MemoiresViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour mémoires."""

    permission_classes = [IsEnseignantOrScolarite]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["sujet", "etudiant", "statut"]
    search_fields = ["resume", "etudiant__user__last_name"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return Memoire.objects.select_related(
            "sujet__encadreur__user", "etudiant__user"
        )

    def get_serializer_class(self):
        if self.action == "list":
            return MemoireListSerializer
        return MemoireDetailSerializer

    @action(detail=True, methods=["post"])
    def soumettre(self, request, pk=None):
        """Soumet le mémoire pour validation."""
        memoire = self.get_object()
        if not memoire.fichier:
            return Response({"error": "Fichier requis."}, status=400)
        memoire.date_depot = timezone.now()
        memoire.statut = "soumis"
        memoire.save(update_fields=["date_depot", "statut"])
        return Response({"detail": "Mémoire soumis.", "id": memoire.id})

    @action(detail=True, methods=["post"])
    def valider(self, request, pk=None):
        """Valide le mémoire."""
        memoire = self.get_object()
        decision = request.data.get("decision", "accepte")
        memoire.statut = decision
        memoire.save(update_fields=["statut"])
        return Response({"detail": f"Mémoire {decision}.", "id": memoire.id})


class JurysMemoireViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour jurys de mémoire."""

    permission_classes = [IsEnseignantOrScolarite]
    serializer_class = JuryMemoireSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["memoire", "president"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return JuryMemoire.objects.select_related(
            "memoire__etudiant__user", "memoire__sujet", "president"
        ).prefetch_related("rapporteurs", "autres_membres")
