"""API views for bulletins (ViewSets DRF) - SIS Secondaire."""

from apps.notes.api import BulletinsViewSet as _BulletinsViewSet
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import AppreciationMatiere
from .serializers import AppreciationMatiereCreateSerializer, AppreciationMatiereSerializer


class IsEnseignantOrScolarite(IsAuthenticated):
    """Permission: enseignant ou scolarité pour écriture."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        user = request.user
        return (
            user.is_staff
            or hasattr(user, "enseignant_profile")
            or getattr(user, "role", "")
            in ("scolarite", "directeur", "proviseur", "principal")
        )


class AppreciationsMatiereViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour appréciations matières."""

    permission_classes = [IsEnseignantOrScolarite]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["eleve", "matiere", "periode", "eleve__classe"]
    ordering = ["eleve__user__last_name", "matiere__nom"]

    def get_queryset(self):
        return AppreciationMatiere.objects.select_related(
            "eleve__user", "matiere", "periode"
        )

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return AppreciationMatiereCreateSerializer
        return AppreciationMatiereSerializer

    @action(detail=False, methods=["get"])
    def par_eleve(self, request):
        """Liste les appréciations groupées par élève."""
        eleve_id = request.query_params.get("eleve")
        periode_id = request.query_params.get("periode")
        if not eleve_id or not periode_id:
            return Response(
                {"error": "Paramètres eleve et periode requis."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        appreciations = (
            self.get_queryset()
            .filter(eleve_id=eleve_id, periode_id=periode_id)
            .order_by("matiere__nom")
        )
        serializer = AppreciationMatiereSerializer(appreciations, many=True)
        return Response(serializer.data)


class BulletinsViewSet(_BulletinsViewSet):
    """Compatibility viewset aligned with active notes bulletins."""

    @action(detail=False, methods=["get"])
    def par_classe(self, request):
        """Liste les appréciations d'une classe pour une matière/période."""
        classe_id = request.query_params.get("classe")
        matiere_id = request.query_params.get("matiere")
        periode_id = request.query_params.get("periode")
        if not all([classe_id, matiere_id, periode_id]):
            return Response(
                {"error": "Paramètres classe, matiere et periode requis."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        appreciations = (
            self.get_queryset()
            .filter(
                eleve__classe_id=classe_id, matiere_id=matiere_id, periode_id=periode_id
            )
            .order_by("rang", "eleve__user__last_name")
        )
        serializer = AppreciationMatiereSerializer(appreciations, many=True)
        return Response(serializer.data)
