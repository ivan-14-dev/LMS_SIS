"""API views for etablissement (ViewSets DRF) - SIS Supérieur."""

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from sis_common.authorization import has_business_permission_or_role

from .models import AnneeUniversitaire, Semestre, Universite
from .serializers import (
    AnneeUniversitaireSerializer,
    SemestreSerializer,
    UniversiteSerializer,
)


class IsAdminOrReadOnly(IsAuthenticated):
    """Permission: admin pour écriture, authentifié pour lecture."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        return has_business_permission_or_role(
            request.user,
            "etablissement.change_universite",
            (
                "president",
                "vice_president",
                "doyen",
                "directeur_etudes",
                "scolarite",
            ),
        )


class IsTenantConfigurationAdmin(IsAuthenticated):
    def has_permission(self, request, view):
        return super().has_permission(
            request, view
        ) and has_business_permission_or_role(
            request.user,
            "etablissement.change_universite",
            (
                "president",
                "vice_president",
                "doyen",
                "directeur_etudes",
                "scolarite",
            ),
        )


class CurrentUniversiteView(APIView):
    """Configuration de l'établissement associé au domaine courant."""

    permission_classes = [IsTenantConfigurationAdmin]

    def get_tenant(self, request):
        if not isinstance(request.tenant, Universite):
            return None
        return request.tenant

    def get(self, request):
        tenant = self.get_tenant(request)
        if tenant is None:
            return Response(
                {"detail": "Aucun établissement n'est associé à ce domaine."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(UniversiteSerializer(tenant, context={"request": request}).data)

    def patch(self, request):
        tenant = self.get_tenant(request)
        if tenant is None:
            return Response(
                {"detail": "Aucun établissement n'est associé à ce domaine."},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = UniversiteSerializer(
            tenant,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class UniversitesViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour universités."""

    permission_classes = [IsAdminOrReadOnly]
    serializer_class = UniversiteSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["type", "pays", "actif"]
    search_fields = ["nom", "sigle", "ville"]
    ordering = ["nom"]

    def get_queryset(self):
        return Universite.objects.prefetch_related("facultes")

    @action(detail=True, methods=["get"])
    def annees(self, request, pk=None):
        """Liste les années universitaires."""
        universite = self.get_object()
        annees = universite.annees_universitaires.all().order_by("-date_debut")
        serializer = AnneeUniversitaireSerializer(annees, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def facultes(self, request, pk=None):
        """Liste les facultés de l'université."""
        universite = self.get_object()
        from apps.structure.serializers import FaculteListSerializer

        facultes = universite.facultes.select_related("doyen").order_by("code")
        serializer = FaculteListSerializer(facultes, many=True)
        return Response(serializer.data)


class AnneesUniversitairesViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour années universitaires."""

    permission_classes = [IsAdminOrReadOnly]
    serializer_class = AnneeUniversitaireSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["universite", "en_cours", "cloturee"]
    ordering = ["-date_debut"]

    def get_queryset(self):
        return AnneeUniversitaire.objects.select_related("universite").filter(
            universite=self.request.tenant
        )

    def perform_create(self, serializer):
        serializer.save(universite=self.request.tenant)

    @action(detail=True, methods=["get"])
    def semestres(self, request, pk=None):
        """Liste les semestres de l'année."""
        annee = self.get_object()
        semestres = annee.semestres.all().order_by("numero")
        serializer = SemestreSerializer(semestres, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def activer(self, request, pk=None):
        """Active l'année universitaire."""
        annee = self.get_object()
        # Désactiver les autres années de la même université
        AnneeUniversitaire.objects.filter(
            universite=annee.universite, en_cours=True
        ).exclude(pk=annee.pk).update(en_cours=False)

        annee.en_cours = True
        annee.save(update_fields=["en_cours"])
        return Response({"detail": "Année activée.", "id": annee.id})

    @action(detail=True, methods=["post"])
    def cloturer(self, request, pk=None):
        """Clôture l'année universitaire."""
        annee = self.get_object()
        if annee.cloturee:
            return Response({"error": "Année déjà clôturée."}, status=400)
        annee.cloturee = True
        annee.en_cours = False
        annee.save(update_fields=["cloturee", "en_cours"])
        return Response({"detail": "Année clôturée.", "id": annee.id})


class SemestresViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour semestres."""

    permission_classes = [IsAdminOrReadOnly]
    serializer_class = SemestreSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["annee_universitaire", "type", "cloture"]
    ordering = ["annee_universitaire", "numero"]

    def get_queryset(self):
        return Semestre.objects.select_related("annee_universitaire").filter(
            annee_universitaire__universite=self.request.tenant
        )

    @action(detail=True, methods=["post"])
    def cloturer(self, request, pk=None):
        """Clôture le semestre."""
        semestre = self.get_object()
        if semestre.cloture:
            return Response({"error": "Semestre déjà clôturé."}, status=400)
        semestre.cloture = True
        semestre.save(update_fields=["cloture"])
        return Response({"detail": "Semestre clôturé.", "id": semestre.id})
