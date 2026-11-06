"""API views for transport (ViewSets DRF) - SIS Secondaire."""

from django.db import IntegrityError, transaction
from django.db.models import Count, Q, Sum
from django.db.models.deletion import ProtectedError
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from sis_common.authorization import is_current_tenant_user, request_has_business_access

from .models import Arret, Chauffeur, InscriptionTransport, LigneTransport, TrajetScolaire, Vehicule
from .serializers import (
    ArretSerializer,
    ChauffeurSerializer,
    InscriptionTransportSerializer,
    LigneTransportDetailSerializer,
    LigneTransportListSerializer,
    TrajetScolaireSerializer,
    VehiculeSerializer,
)


class IsIntendanceOrReadOnly(IsAuthenticated):
    """Permission: intendance pour écriture."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view) or not is_current_tenant_user(request):
            return False
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        return self.has_management_permission(request)

    @staticmethod
    def has_management_permission(request):
        return request_has_business_access(
            request,
            "transport.change_lignetransport",
            ("intendance", "vie_scolaire", "directeur", "proviseur", "principal"),
            tenant_group_codes=("transport_manager_secondary",),
        )


class CanManageOrViewChauffeurs(IsIntendanceOrReadOnly):
    """Réserver les coordonnées des chauffeurs aux comptes habilités."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return self.has_management_permission(request) or request_has_business_access(
                request, "transport.view_chauffeur"
            )
        return True


class LignesTransportViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour lignes de transport."""

    permission_classes = [IsIntendanceOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["actif"]
    search_fields = ["nom", "itineraire"]
    ordering = ["nom"]

    def get_queryset(self):
        return LigneTransport.objects.annotate(
            _nb_arrets=Count("arrets"),
            _nb_inscrits=Count("inscriptions", filter=Q(inscriptions__actif=True)),
        )

    def get_serializer_class(self):
        if self.action == "list":
            return LigneTransportListSerializer
        return LigneTransportDetailSerializer

    @action(detail=True, methods=["get"])
    def inscrits(self, request, pk=None):
        """Liste les élèves inscrits sur cette ligne."""
        ligne = self.get_object()
        inscriptions = (
            ligne.inscriptions.filter(actif=True)
            .select_related("eleve__user", "eleve__classe_actuelle", "arret_montee", "arret_descente")
            .order_by("arret_montee__ordre")
        )
        serializer = InscriptionTransportSerializer(inscriptions, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def vehicules(self, request, pk=None):
        """Liste les véhicules affectés à cette ligne."""
        ligne = self.get_object()
        vehicules = ligne.vehicules.all()
        serializer = VehiculeSerializer(vehicules, many=True)
        return Response(serializer.data)


class ArretsViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour arrêts."""

    permission_classes = [IsIntendanceOrReadOnly]
    serializer_class = ArretSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["ligne"]
    ordering = ["ligne", "ordre"]

    def get_queryset(self):
        return Arret.objects.select_related("ligne")


class VehiculesViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour véhicules."""

    permission_classes = [IsIntendanceOrReadOnly]
    serializer_class = VehiculeSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["ligne", "gps_actif"]
    search_fields = ["immatriculation", "modele", "chauffeur"]
    ordering = ["immatriculation"]

    def get_queryset(self):
        return Vehicule.objects.select_related("ligne")


class ChauffeursViewSet(viewsets.ModelViewSet):
    """Référentiel de conducteurs du locataire courant."""

    permission_classes = [CanManageOrViewChauffeurs]
    serializer_class = ChauffeurSerializer
    queryset = Chauffeur.objects.all()
    filter_backends = [SearchFilter]
    search_fields = ["nom"]

    def perform_destroy(self, instance):
        try:
            instance.delete()
        except ProtectedError as exc:
            raise ValidationError(
                {"chauffeur": "Ce chauffeur est encore affecté à un trajet."}
            ) from exc


class TrajetsScolairesViewSet(viewsets.ModelViewSet):
    """Affectations ponctuelles de véhicules et, facultativement, de conducteurs."""

    permission_classes = [IsIntendanceOrReadOnly]
    serializer_class = TrajetScolaireSerializer
    queryset = TrajetScolaire.objects.select_related("ligne", "vehicule", "chauffeur")
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["ligne", "vehicule", "chauffeur"]
    ordering = ["depart_at", "id"]

    def _save_trip(self, serializer):
        try:
            with transaction.atomic():
                serializer.save()
        except IntegrityError as exc:
            constraint = getattr(getattr(exc.__cause__, "diag", None), "constraint_name", None)
            if constraint == "transport_trajet_vehicle_no_overlap":
                raise ValidationError(
                    {"vehicule": "Ce véhicule est déjà affecté pendant ce trajet."}
                ) from exc
            if constraint == "transport_trajet_driver_no_overlap":
                raise ValidationError(
                    {"chauffeur": "Ce chauffeur est déjà affecté pendant ce trajet."}
                ) from exc
            raise

    def perform_create(self, serializer):
        self._save_trip(serializer)

    def perform_update(self, serializer):
        self._save_trip(serializer)


class InscriptionsTransportViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour inscriptions transport."""

    permission_classes = [IsIntendanceOrReadOnly]
    serializer_class = InscriptionTransportSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["ligne", "eleve", "annee_scolaire", "actif"]
    ordering = ["eleve__user__last_name"]

    def get_queryset(self):
        queryset = InscriptionTransport.objects.select_related(
            "eleve__user",
            "eleve__classe_actuelle",
            "ligne",
            "arret_montee",
            "arret_descente",
            "annee_scolaire",
        )
        if self.action in ("update", "partial_update"):
            return queryset.select_for_update(of=("self",))
        return queryset

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    def _check_available_seat(self, serializer):
        attrs = serializer.validated_data
        existing = serializer.instance
        ligne = attrs.get("ligne", existing.ligne if existing else None)
        year = attrs.get("annee_scolaire", existing.annee_scolaire if existing else None)
        active = attrs.get("actif", existing.actif if existing else True)
        if not active or not ligne or not year:
            return
        if existing and existing.actif and existing.ligne_id == ligne.pk and existing.annee_scolaire_id == year.pk:
            return

        LigneTransport.objects.select_for_update().get(pk=ligne.pk)
        capacity = Vehicule.objects.filter(ligne=ligne).aggregate(total=Sum("capacite"))["total"] or 0
        occupied = InscriptionTransport.objects.filter(
            ligne=ligne, annee_scolaire=year, actif=True
        )
        if existing:
            occupied = occupied.exclude(pk=existing.pk)
        if occupied.count() >= capacity:
            raise ValidationError({"ligne": "Aucune place disponible sur cette ligne pour cette année scolaire."})

    def perform_create(self, serializer):
        self._check_available_seat(serializer)
        serializer.save()

    def perform_update(self, serializer):
        self._check_available_seat(serializer)
        serializer.save()

    @action(detail=False, methods=["get"])
    def statistiques(self, request):
        """Statistiques des inscriptions transport."""
        qs = self.get_queryset().filter(actif=True)
        stats = {
            "total_inscrits": qs.count(),
        }
        by_ligne = qs.values("ligne__nom").annotate(count=Count("id"))
        stats["par_ligne"] = {line["ligne__nom"]: line["count"] for line in by_ligne}
        return Response(stats)
