"""API views for bulletins (ViewSets DRF) - SIS Secondaire."""

from apps.notes.api import BulletinsViewSet as _BulletinsViewSet
from apps.notes.models import Bulletin
from django.db.models import Exists, OuterRef
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import AppreciationMatiere
from .serializers import AppreciationMatiereCreateSerializer, AppreciationMatiereSerializer


def _visible_appreciations(queryset, request):
    tenant = getattr(request, "tenant", None)
    user = request.user
    if tenant is None or user.etablissement_id != tenant.pk:
        return queryset.none()

    queryset = queryset.filter(
        eleve__etablissement_id=tenant.pk,
        periode__annee_scolaire__etablissement_id=tenant.pk,
    )
    if user.role == "eleve" and not user.is_superuser:
        queryset = queryset.filter(eleve__user=user)
    elif user.role == "parent" or hasattr(user, "tuteur_profile"):
        queryset = queryset.filter(
            eleve__tuteurs_lies__tuteur__user=user,
            eleve__tuteurs_lies__autorise_acces_portail=True,
        ).distinct()
    elif not (
        user.is_staff
        or user.is_superuser
        or user.role in (
            "enseignant", "scolarite", "direction", "responsable_pedagogique",
            "vie_scolaire", "directeur", "proviseur", "principal",
        )
    ):
        return queryset.none()
    else:
        return queryset

    return queryset.filter(
        Exists(
            Bulletin.objects.filter(
                eleve_id=OuterRef("eleve_id"),
                periode_id=OuterRef("periode_id"),
                publie=True,
            )
        )
    )


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
            or getattr(user, "role", "") in ("scolarite", "directeur", "proviseur", "principal")
        )


class AppreciationsMatiereViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour appréciations matières."""

    permission_classes = [IsEnseignantOrScolarite]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["eleve", "matiere", "periode", "eleve__classe_actuelle"]
    ordering = ["eleve__user__last_name", "matiere__nom"]

    def get_queryset(self):
        return _visible_appreciations(
            AppreciationMatiere.objects.select_related("eleve__user", "matiere", "periode"),
            self.request,
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
        appreciations = self.get_queryset().filter(eleve_id=eleve_id, periode_id=periode_id).order_by("matiere__nom")
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
        appreciations = _visible_appreciations(
            AppreciationMatiere.objects.select_related("eleve__user", "matiere", "periode"),
            request,
        )
        appreciations = (
            appreciations
            .filter(eleve__classe_actuelle_id=classe_id, matiere_id=matiere_id, periode_id=periode_id)
            .order_by("rang", "eleve__user__last_name")
        )
        serializer = AppreciationMatiereSerializer(appreciations, many=True)
        return Response(serializer.data)
