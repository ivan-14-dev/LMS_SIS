"""API views for stages (ViewSets DRF) - SIS Secondaire."""

from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from sis_common.authorization import request_has_business_access

from .models import ConventionStage, Entreprise, EvaluationStage, SuiviStage
from .serializers import (
    ConventionStageDetailSerializer,
    ConventionStageListSerializer,
    EntrepriseSerializer,
    EvaluationStageSerializer,
    SuiviStageSerializer,
)


class IsScolariteOrReadOnly(IsAuthenticated):
    """Permission: scolarité ou responsable stages pour écriture."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        return request_has_business_access(
            request,
            "stages.change_conventionstage",
            ("scolarite", "responsable_stages", "chef_travaux", "directeur"),
            tenant_group_codes=("stage_manager_secondary",),
        )


class EntreprisesStageViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour entreprises de stage."""

    permission_classes = [IsScolariteOrReadOnly]
    serializer_class = EntrepriseSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["secteur", "ville"]
    search_fields = ["raison_sociale", "siret", "ville"]
    ordering = ["raison_sociale"]

    def get_queryset(self):
        return Entreprise.objects.prefetch_related("conventions")


class ConventionsStageViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour conventions de stage."""

    permission_classes = [IsScolariteOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["eleve", "entreprise", "statut", "maitre_stage_etablissement"]
    search_fields = ["eleve__user__last_name", "entreprise__raison_sociale"]
    ordering = ["-date_debut"]

    def get_queryset(self):
        return ConventionStage.objects.select_related(
            "eleve__user", "entreprise", "maitre_stage_etablissement"
        ).prefetch_related("suivis")

    def get_serializer_class(self):
        if self.action == "list":
            return ConventionStageListSerializer
        return ConventionStageDetailSerializer

    @action(detail=True, methods=["post"])
    def signer(self, request, pk=None):
        """Progresse la signature de la convention."""
        convention = self.get_object()
        request.data.get("signataire")  # eleve, entreprise, etablissement

        progression = {
            "brouillon": "signee_etudiant",
            "signee_etudiant": "signee_entreprise",
            "signee_entreprise": "signee_etablissement",
            "signee_etablissement": "complete",
        }

        if convention.statut in progression:
            convention.statut = progression[convention.statut]
            if convention.statut == "complete":
                convention.date_signature_complete = timezone.now()
            convention.save()
            return Response(
                {"detail": f"Convention {convention.statut}.", "id": convention.id}
            )

        return Response({"error": "Impossible de signer."}, status=400)

    @action(detail=True, methods=["get"])
    def suivis(self, request, pk=None):
        """Liste les suivis de la convention."""
        convention = self.get_object()
        suivis = convention.suivis.all().order_by("-date")
        serializer = SuiviStageSerializer(suivis, many=True)
        return Response(serializer.data)


class SuivisStageViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour suivis de stage."""

    permission_classes = [IsScolariteOrReadOnly]
    serializer_class = SuiviStageSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["convention", "type"]
    ordering = ["-date"]

    def get_queryset(self):
        return SuiviStage.objects.select_related("convention__eleve__user")


class EvaluationsStageViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour évaluations de stage."""

    permission_classes = [IsScolariteOrReadOnly]
    serializer_class = EvaluationStageSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["convention"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return EvaluationStage.objects.select_related(
            "convention__eleve__user", "convention__entreprise"
        )

    def perform_create(self, serializer):
        evaluation = serializer.save()
        # Calculer note finale si toutes les notes sont là
        if all(
            [
                evaluation.note_entreprise,
                evaluation.note_etablissement,
                evaluation.note_soutenance,
            ]
        ):
            evaluation.note_finale = (
                evaluation.note_entreprise * 0.4
                + evaluation.note_etablissement * 0.3
                + evaluation.note_soutenance * 0.3
            )
            evaluation.save(update_fields=["note_finale"])
