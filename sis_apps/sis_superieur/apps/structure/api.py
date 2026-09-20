"""API views for structure (ViewSets DRF) - SIS Supérieur."""

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from sis_common.authorization import has_business_permission_or_role

from .models import Departement, EcoleDoctorale, Faculte
from .serializers import DepartementSerializer, EcoleDoctoraleSerializer, FaculteDetailSerializer, FaculteListSerializer


class IsAdminOrReadOnly(IsAuthenticated):
    """Permission: admin pour écriture, authentifié pour lecture."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        return has_business_permission_or_role(
            request.user,
            "structure.change_faculte",
            (
                "president",
                "vice_president",
                "doyen",
                "directeur_etudes",
                "scolarite",
            ),
        )


class FacultesViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour facultés."""

    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["universite", "actif"]
    search_fields = ["code", "nom"]
    ordering = ["code"]

    def get_queryset(self):
        return Faculte.objects.select_related("universite", "doyen").filter(universite=self.request.tenant)

    def get_serializer_class(self):
        if self.action == "list":
            return FaculteListSerializer
        return FaculteDetailSerializer

    @action(detail=True, methods=["get"])
    def departements(self, request, pk=None):
        """Liste les départements de la faculté."""
        faculte = self.get_object()
        departements = faculte.departements.select_related("directeur").order_by("code")
        serializer = DepartementSerializer(departements, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def formations(self, request, pk=None):
        """Liste les formations de la faculté (via ses départements)."""
        faculte = self.get_object()
        from apps.formations.models import Formation
        from apps.formations.serializers import FormationListSerializer

        formations = Formation.objects.filter(departement__faculte=faculte).select_related("departement", "responsable")
        serializer = FormationListSerializer(formations, many=True)
        return Response(serializer.data)


class DepartementsViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour départements."""

    permission_classes = [IsAdminOrReadOnly]
    serializer_class = DepartementSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["faculte"]
    search_fields = ["code", "nom"]
    ordering = ["code"]

    def get_queryset(self):
        return Departement.objects.select_related("faculte", "directeur").filter(
            faculte__universite=self.request.tenant
        )

    @action(detail=True, methods=["get"])
    def formations(self, request, pk=None):
        """Liste les formations du département."""
        departement = self.get_object()
        from apps.formations.serializers import FormationListSerializer

        formations = departement.formations.select_related("responsable")
        serializer = FormationListSerializer(formations, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def enseignants(self, request, pk=None):
        """Liste les enseignants du département."""
        departement = self.get_object()
        from apps.enseignants.models import EnseignantChercheur
        from apps.enseignants.serializers import EnseignantListSerializer

        enseignants = EnseignantChercheur.objects.filter(
            affectations__ue__maquette__formation__departement=departement
        ).select_related("user")
        serializer = EnseignantListSerializer(enseignants, many=True)
        return Response(serializer.data)


class EcolesDoctoralesViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour écoles doctorales."""

    permission_classes = [IsAdminOrReadOnly]
    serializer_class = EcoleDoctoraleSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["universite"]
    search_fields = ["code", "nom"]
    ordering = ["code"]

    def get_queryset(self):
        return EcoleDoctorale.objects.select_related("universite", "directeur").filter(universite=self.request.tenant)
