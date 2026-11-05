"""API views for etablissement (ViewSets DRF) - SIS Supérieur."""

from django.db import transaction
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from sis_common.academic_configuration import catalog_options
from sis_common.academic_lifecycle import AcademicLifecycleMixin, ensure_academic_open
from sis_common.authorization import has_business_permission_or_role
from sis_common.hierarchy_api import ConfigurationHierarchyMixin, OrganizationUnitsViewSet
from sis_common.institutional_profiles import OfferingPreviewMixin
from sis_common.module_configuration import ModuleConfigurationMixin
from sis_common.workflow_tracking import record_workflow_event

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
        return super().has_permission(request, view) and has_business_permission_or_role(
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


class OfferingPreviewView(OfferingPreviewMixin, CurrentUniversiteView):
    """Simulation des règles d'une offre, réservée aux administrateurs du tenant."""


class ModulesView(ModuleConfigurationMixin, CurrentUniversiteView):
    """Activation des modules installés pour l'établissement courant."""


class ConfigurationHierarchyView(ConfigurationHierarchyMixin, CurrentUniversiteView):
    """Simulation et publication des règles héritées."""


class UnitsViewSet(OrganizationUnitsViewSet):
    permission_classes = [IsAdminOrReadOnly]


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


class AnneesUniversitairesViewSet(AcademicLifecycleMixin, viewsets.ModelViewSet):
    """ViewSet CRUD pour années universitaires."""

    permission_classes = [IsAdminOrReadOnly]
    serializer_class = AnneeUniversitaireSerializer
    academic_period_paths = ("",)
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["universite", "en_cours", "cloturee"]
    ordering = ["-date_debut"]

    def get_queryset(self):
        return AnneeUniversitaire.objects.select_related("universite").filter(universite=self.request.tenant)

    def perform_create(self, serializer):
        self.save_academic(serializer, universite=self.request.tenant)

    @action(detail=True, methods=["get"])
    def semestres(self, request, pk=None):
        """Liste les semestres de l'année."""
        annee = self.get_object()
        semestres = annee.semestres.all().order_by("numero")
        serializer = SemestreSerializer(semestres, many=True, context=self.get_serializer_context())
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def activer(self, request, pk=None):
        """Active l'année universitaire."""
        type(request.tenant).objects.select_for_update().get(pk=request.tenant.pk)
        annee = self.get_object()
        if annee.cloturee:
            return Response({"error": "Une année clôturée ne peut pas être réactivée."}, status=400)
        # Désactiver les autres années de la même université
        AnneeUniversitaire.objects.filter(universite=annee.universite, en_cours=True).exclude(pk=annee.pk).update(
            en_cours=False
        )

        annee.en_cours = True
        annee.save(update_fields=["en_cours"])
        record_workflow_event(request, annee, "activation", "Année activée")
        return Response({"detail": "Année activée.", "id": annee.id})

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def cloturer(self, request, pk=None):
        """Clôture l'année universitaire."""
        type(request.tenant).objects.select_for_update().get(pk=request.tenant.pk)
        annee = self.get_object()
        if annee.cloturee:
            return Response({"error": "Année déjà clôturée."}, status=400)
        annee.cloturee = True
        annee.en_cours = False
        annee.save(update_fields=["cloturee", "en_cours"])
        record_workflow_event(request, annee, "cloture", "Année clôturée")
        return Response({"detail": "Année clôturée.", "id": annee.id})


class SemestresViewSet(AcademicLifecycleMixin, viewsets.ModelViewSet):
    """ViewSet CRUD pour semestres."""

    permission_classes = [IsAdminOrReadOnly]
    serializer_class = SemestreSerializer
    academic_period_paths = ("", "annee_universitaire")
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["annee_universitaire", "type", "cloture"]
    ordering = ["annee_universitaire", "numero"]

    def get_queryset(self):
        return Semestre.objects.select_related("annee_universitaire").filter(
            annee_universitaire__universite=self.request.tenant
        )

    @action(detail=False, methods=["get"])
    def types(self, request):
        options = catalog_options(request.tenant.configuration_academique, "period_types", Semestre.TYPE_CHOICES)
        return Response([{"code": item["code"], "label": item["label"]} for item in options])

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def cloturer(self, request, pk=None):
        """Clôture le semestre."""
        semestre = self.get_object()
        ensure_academic_open(semestre, paths=self.academic_period_paths)
        if semestre.cloture:
            return Response({"error": "Semestre déjà clôturé."}, status=400)
        semestre.cloture = True
        semestre.save(update_fields=["cloture"])
        record_workflow_event(request, semestre, "cloture", "Semestre clôturé")
        return Response({"detail": "Semestre clôturé.", "id": semestre.id})
