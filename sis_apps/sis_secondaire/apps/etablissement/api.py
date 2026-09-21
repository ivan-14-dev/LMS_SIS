"""API views for etablissement (ViewSets DRF) - SIS Secondaire."""

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from sis_common.authorization import has_business_permission_or_role

from .models import AnneeScolaire, Etablissement, Niveau, Periode
from .serializers import (
    AnneeScolaireSerializer,
    EtablissementSerializer,
    NiveauSerializer,
    PeriodeSerializer,
)


class IsAdminOrReadOnly(IsAuthenticated):
    """Permission: admin pour écriture."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        return has_business_permission_or_role(
            request.user,
            "etablissement.change_etablissement",
            ("direction", "responsable_pedagogique"),
        )


class IsTenantConfigurationAdmin(IsAuthenticated):
    def has_permission(self, request, view):
        return super().has_permission(request, view) and has_business_permission_or_role(
            request.user,
            "etablissement.change_etablissement",
            ("direction", "responsable_pedagogique"),
        )


class CurrentEtablissementView(APIView):
    """Configuration de l'établissement associé au domaine courant."""

    permission_classes = [IsTenantConfigurationAdmin]

    def get_tenant(self, request):
        if not isinstance(request.tenant, Etablissement):
            return None
        return request.tenant

    def get(self, request):
        tenant = self.get_tenant(request)
        if tenant is None:
            return Response(
                {"detail": "Aucun établissement n'est associé à ce domaine."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(EtablissementSerializer(tenant, context={"request": request}).data)

    def patch(self, request):
        tenant = self.get_tenant(request)
        if tenant is None:
            return Response(
                {"detail": "Aucun établissement n'est associé à ce domaine."},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = EtablissementSerializer(
            tenant,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class EtablissementsViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour établissements."""

    permission_classes = [IsAdminOrReadOnly]
    serializer_class = EtablissementSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["type", "pays", "actif"]
    search_fields = ["nom", "uai", "ville"]
    ordering = ["nom"]

    def get_queryset(self):
        return Etablissement.objects.prefetch_related("annees_scolaires")

    @action(detail=True, methods=["get"])
    def annees(self, request, pk=None):
        """Liste les années scolaires."""
        etablissement = self.get_object()
        annees = etablissement.annees_scolaires.all().order_by("-date_debut")
        serializer = AnneeScolaireSerializer(annees, many=True)
        return Response(serializer.data)


class AnneesScolairesViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour années scolaires."""

    permission_classes = [IsAdminOrReadOnly]
    serializer_class = AnneeScolaireSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["etablissement", "en_cours", "cloturee"]
    ordering = ["-date_debut"]

    def get_queryset(self):
        return AnneeScolaire.objects.select_related("etablissement").filter(etablissement=self.request.tenant)

    def perform_create(self, serializer):
        serializer.save(etablissement=self.request.tenant)

    @action(detail=True, methods=["get"])
    def periodes(self, request, pk=None):
        """Liste les périodes de l'année."""
        annee = self.get_object()
        periodes = annee.periodes.all().order_by("numero")
        serializer = PeriodeSerializer(periodes, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def activer(self, request, pk=None):
        """Active l'année scolaire."""
        annee = self.get_object()
        # Désactiver les autres années du même établissement
        AnneeScolaire.objects.filter(etablissement=annee.etablissement, en_cours=True).exclude(pk=annee.pk).update(
            en_cours=False
        )

        annee.en_cours = True
        annee.save(update_fields=["en_cours"])
        return Response({"detail": "Année activée.", "id": annee.id})

    @action(detail=True, methods=["post"])
    def cloturer(self, request, pk=None):
        """Clôture l'année scolaire."""
        annee = self.get_object()
        if annee.cloturee:
            return Response({"error": "Année déjà clôturée."}, status=400)
        annee.cloturee = True
        annee.en_cours = False
        annee.save(update_fields=["cloturee", "en_cours"])
        return Response({"detail": "Année clôturée.", "id": annee.id})


class PeriodesViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour périodes."""

    permission_classes = [IsAdminOrReadOnly]
    serializer_class = PeriodeSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["annee_scolaire", "type", "cloturee"]
    ordering = ["annee_scolaire", "numero"]

    def get_queryset(self):
        return Periode.objects.select_related("annee_scolaire").filter(
            annee_scolaire__etablissement=self.request.tenant
        )

    @action(detail=True, methods=["post"])
    def cloturer(self, request, pk=None):
        """Clôture la période."""
        periode = self.get_object()
        if periode.cloturee:
            return Response({"error": "Période déjà clôturée."}, status=400)
        periode.cloturee = True
        periode.save(update_fields=["cloturee"])
        return Response({"detail": "Période clôturée.", "id": periode.id})


class NiveauxViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour niveaux."""

    permission_classes = [IsAdminOrReadOnly]
    serializer_class = NiveauSerializer

    def get_queryset(self):
        return Niveau.objects.filter(etablissement=self.request.tenant).order_by("ordre", "code")

    def perform_create(self, serializer):
        serializer.save(etablissement=self.request.tenant)
