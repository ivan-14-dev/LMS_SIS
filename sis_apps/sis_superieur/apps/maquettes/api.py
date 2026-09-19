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

from .serializers import MaquetteSerializer


class IsScolariteOrReadOnly(IsAuthenticated):
    """Permission: scolarité pour écriture."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        user = request.user
        return user.is_staff or getattr(user, "role", "") in (
            "scolarite",
            "directeur_etudes",
            "chef_departement",
            "doyen",
        )


class MaquettesViewSet(viewsets.ModelViewSet):
    """ViewSet pour les maquettes de formation."""

    permission_classes = [IsScolariteOrReadOnly]
    serializer_class = MaquetteSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["formation", "semestre", "obligatoire"]
    ordering = ["semestre", "ordre"]

    def get_queryset(self):
        return MaquetteFormation.objects.select_related(
            "formation", "semestre", "ecue__ue"
        )

    @action(detail=False, methods=["get"])
    def par_formation(self, request):
        """Maquette complète d'une formation."""
        formation_id = request.query_params.get("formation_id")
        if not formation_id:
            return Response({"error": "formation_id requis."}, status=400)

        maquettes = (
            self.get_queryset()
            .filter(formation_id=formation_id)
            .order_by("semestre__numero", "ordre")
        )

        serializer = self.get_serializer(maquettes, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def par_semestre(self, request):
        """Maquette d'un semestre."""
        formation_id = request.query_params.get("formation_id")
        semestre_id = request.query_params.get("semestre_id")

        if not formation_id or not semestre_id:
            return Response(
                {"error": "formation_id et semestre_id requis."}, status=400
            )

        maquettes = (
            self.get_queryset()
            .filter(formation_id=formation_id, semestre_id=semestre_id)
            .order_by("ordre")
        )

        serializer = self.get_serializer(maquettes, many=True)
        return Response(serializer.data)
