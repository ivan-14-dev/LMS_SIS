"""API views for maquettes (SIS Supérieur).

Note: Utilise MaquetteFormation du module formations.
Fournit des vues pour la gestion des maquettes pédagogiques.
"""

from apps.formations.models import MaquetteFormation
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from sis_common.academic_lifecycle import AcademicLifecycleMixin
from sis_common.authorization import request_has_business_access

from .serializers import MaquetteSerializer


class IsScolariteOrReadOnly(IsAuthenticated):
    """Permission: scolarité pour écriture."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        return request_has_business_access(
            request,
            "formations.change_maquetteformation",
            ("scolarite", "directeur_etudes", "chef_departement", "doyen"),
            tenant_group_codes=("curriculum_manager_superieur",),
        )


class MaquettesViewSet(AcademicLifecycleMixin, viewsets.ModelViewSet):
    """ViewSet pour les maquettes de formation."""

    permission_classes = [IsScolariteOrReadOnly]
    serializer_class = MaquetteSerializer
    academic_period_paths = ("annee_universitaire",)
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["formation", "annee_universitaire", "statut"]
    ordering = ["-annee_universitaire__date_debut", "formation__nom"]

    def get_queryset(self):
        return MaquetteFormation.objects.filter(
            annee_universitaire__universite=self.request.tenant
        ).select_related("formation", "annee_universitaire")

    @action(detail=False, methods=["get"])
    def par_formation(self, request):
        """Maquette complète d'une formation."""
        formation_id = request.query_params.get("formation_id")
        if not formation_id:
            return Response({"error": "formation_id requis."}, status=400)

        maquettes = self.get_queryset().filter(formation_id=formation_id).order_by("-annee_universitaire__date_debut")

        serializer = self.get_serializer(maquettes, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def par_semestre(self, request):
        """The persisted curriculum is annual, not a row per semester."""
        return Response(
            {"error": "Utilisez par_formation : la structure des semestres est contenue dans la maquette annuelle."},
            status=400,
        )
