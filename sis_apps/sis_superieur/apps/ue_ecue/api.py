"""API views for UE/ECUE (ViewSets DRF) - SIS Supérieur."""

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import ECUE, UE, Prerequis
from .serializers import ECUESerializer, PrerequisSerializer, UEDetailSerializer, UEListSerializer


class IsScolariteOrReadOnly(IsAuthenticated):
    """Permission: scolarité pour écriture, authentifié pour lecture."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        user = request.user
        return user.is_staff or getattr(user, "role", "") in (
            "scolarite",
            "directeur_etudes",
            "responsable_formation",
            "doyen",
        )


class UEViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour UE."""

    permission_classes = [IsScolariteOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["maquette", "semestre", "type"]
    search_fields = ["code", "nom", "description"]
    ordering_fields = ["code", "semestre", "credits_ects"]
    ordering = ["semestre", "code"]

    def get_queryset(self):
        return UE.objects.select_related(
            "maquette__formation", "semestre"
        ).prefetch_related("parcours_autorises")

    def get_serializer_class(self):
        if self.action == "list":
            return UEListSerializer
        return UEDetailSerializer

    @action(detail=True, methods=["get"])
    def ecues(self, request, pk=None):
        """Liste les ECUE de l'UE."""
        ue = self.get_object()
        ecues = ue.ecues.all().order_by("code")
        serializer = ECUESerializer(ecues, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def prerequis(self, request, pk=None):
        """Liste les prérequis de l'UE."""
        ue = self.get_object()
        prerequis = ue.prerequis_requis.select_related("ue_prereq")
        serializer = PrerequisSerializer(prerequis, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def est_prerequis_de(self, request, pk=None):
        """Liste les UE pour lesquelles cette UE est prérequis."""
        ue = self.get_object()
        prerequis = ue.est_prerequis_de.select_related("ue_cible")
        serializer = PrerequisSerializer(prerequis, many=True)
        return Response(serializer.data)


class ECUEViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour ECUE."""

    permission_classes = [IsScolariteOrReadOnly]
    serializer_class = ECUESerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["ue", "ue__maquette", "ue__semestre"]
    search_fields = ["code", "nom", "description"]
    ordering = ["ue__code", "code"]

    def get_queryset(self):
        return ECUE.objects.select_related("ue")

    @action(detail=True, methods=["get"])
    def enseignants(self, request, pk=None):
        """Liste les enseignants affectés à l'ECUE."""
        ecue = self.get_object()
        from apps.enseignants.models import AffectationEnseignement
        from apps.enseignants.serializers import AffectationEnseignementSerializer

        affectations = AffectationEnseignement.objects.filter(ecue=ecue).select_related(
            "enseignant__user"
        )
        serializer = AffectationEnseignementSerializer(affectations, many=True)
        return Response(serializer.data)


class PrerequisViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour prérequis."""

    permission_classes = [IsScolariteOrReadOnly]
    serializer_class = PrerequisSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["ue_cible", "ue_prereq", "type"]

    def get_queryset(self):
        return Prerequis.objects.select_related("ue_cible", "ue_prereq")
