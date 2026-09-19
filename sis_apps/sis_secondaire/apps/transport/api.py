"""API views for transport (ViewSets DRF) - SIS Secondaire."""

from django.db.models import Count, Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Arret, InscriptionTransport, LigneTransport, Vehicule
from .serializers import (
    ArretSerializer,
    InscriptionTransportSerializer,
    LigneTransportDetailSerializer,
    LigneTransportListSerializer,
    VehiculeSerializer,
)


class IsIntendanceOrReadOnly(IsAuthenticated):
    """Permission: intendance pour écriture."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        user = request.user
        return user.is_staff or getattr(user, "role", "") in (
            "intendance",
            "vie_scolaire",
            "directeur",
            "proviseur",
            "principal",
        )


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
            .select_related(
                "eleve__user", "eleve__classe", "arret_montee", "arret_descente"
            )
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


class InscriptionsTransportViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour inscriptions transport."""

    permission_classes = [IsIntendanceOrReadOnly]
    serializer_class = InscriptionTransportSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["ligne", "eleve", "annee_scolaire", "actif"]
    ordering = ["eleve__user__last_name"]

    def get_queryset(self):
        return InscriptionTransport.objects.select_related(
            "eleve__user",
            "eleve__classe",
            "ligne",
            "arret_montee",
            "arret_descente",
            "annee_scolaire",
        )

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
