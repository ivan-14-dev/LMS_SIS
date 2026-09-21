"""API views for classes (ViewSets DRF) - SIS Secondaire."""

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from sis_common.authorization import request_has_business_access

from .models import Classe, Groupe, Matiere, ProgrammeMatiere
from .serializers import (
    ClasseDetailSerializer,
    ClasseListSerializer,
    GroupeSerializer,
    MatiereDetailSerializer,
    MatiereListSerializer,
    ProgrammeMatiereSerializer,
)


class IsVieScolariteOrReadOnly(IsAuthenticated):
    """Permission: vie scolaire pour écriture, authentifié pour lecture."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        return request_has_business_access(
            request,
            "classes.change_classe",
            ("vie_scolaire", "directeur", "proviseur", "principal", "cpe"),
            tenant_group_codes=("class_manager_secondary",),
        )


class ClassesViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour classes."""

    permission_classes = [IsVieScolariteOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["niveau", "annee_scolaire", "prof_principal"]
    search_fields = ["nom"]
    ordering_fields = ["nom", "niveau__ordre", "created_at"]
    ordering = ["niveau__ordre", "nom"]

    def get_queryset(self):
        qs = Classe.objects.select_related("niveau", "annee_scolaire", "prof_principal", "salle_principale")
        # Filtrer par établissement du tenant
        if hasattr(self.request, "tenant"):
            qs = qs.filter(etablissement=self.request.tenant)
        return qs

    def get_serializer_class(self):
        if self.action == "list":
            return ClasseListSerializer
        return ClasseDetailSerializer

    @action(detail=True, methods=["get"])
    def eleves(self, request, pk=None):
        """Liste les élèves de la classe."""
        from apps.eleves.serializers import EleveListSerializer

        classe = self.get_object()
        eleves = classe.eleves_actuels.select_related("user").order_by("user__last_name")
        serializer = EleveListSerializer(eleves, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def programmes(self, request, pk=None):
        """Liste les programmes de matières de la classe."""
        classe = self.get_object()
        programmes = (
            classe.programmes.select_related("matiere", "enseignant_principal")
            .prefetch_related("enseignants")
            .order_by("matiere__nom")
        )
        serializer = ProgrammeMatiereSerializer(programmes, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def statistiques(self, request, pk=None):
        """Statistiques de la classe."""
        classe = self.get_object()
        eleves = classe.eleves_actuels.all()
        return Response(
            {
                "classe_id": classe.id,
                "classe_nom": classe.nom,
                "effectif": eleves.count(),
                "effectif_max": classe.effectif_max,
                "garcons": eleves.filter(sexe="M").count(),
                "filles": eleves.filter(sexe="F").count(),
                "boursiers": eleves.filter(bourse=True).count(),
                "demi_pensionnaires": eleves.filter(cantine=True).count(),
                "internes": eleves.filter(interne=True).count(),
            }
        )


class GroupesViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour groupes."""

    permission_classes = [IsVieScolariteOrReadOnly]
    serializer_class = GroupeSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["type", "annee_scolaire"]
    search_fields = ["nom"]

    def get_queryset(self):
        qs = Groupe.objects.prefetch_related("classes")
        if hasattr(self.request, "tenant"):
            qs = qs.filter(etablissement=self.request.tenant)
        return qs


class MatieresViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour matières."""

    permission_classes = [IsVieScolariteOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["type"]
    search_fields = ["code", "nom"]
    ordering_fields = ["nom", "code"]
    ordering = ["nom"]

    def get_queryset(self):
        qs = Matiere.objects.all()
        if hasattr(self.request, "tenant"):
            qs = qs.filter(etablissement=self.request.tenant)
        return qs

    def get_serializer_class(self):
        if self.action == "list":
            return MatiereListSerializer
        return MatiereDetailSerializer


class ProgrammesViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour programmes de matières."""

    permission_classes = [IsVieScolariteOrReadOnly]
    serializer_class = ProgrammeMatiereSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["classe", "matiere", "obligatoire"]

    def get_queryset(self):
        return ProgrammeMatiere.objects.select_related("classe", "matiere", "enseignant_principal").prefetch_related(
            "enseignants"
        )
