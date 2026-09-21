"""API views for internat (ViewSets DRF) - SIS Secondaire."""

from django.db.models import Count, F, Q
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from sis_common.authorization import request_has_business_access

from .models import BatimentInternat, Chambre, EtudeSurveillee, OccupantChambre
from .serializers import (
    BatimentInternatSerializer,
    ChambreDetailSerializer,
    ChambreListSerializer,
    EtudeSurveilleeSerializer,
    OccupantChambreSerializer,
)


class IsVieScolariteOrReadOnly(IsAuthenticated):
    """Permission: vie scolaire pour écriture."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        return request_has_business_access(
            request,
            "internat.change_chambre",
            ("vie_scolaire", "cpe", "directeur", "proviseur", "principal", "surveillant"),
            tenant_group_codes=("boarding_manager_secondary",),
        )


class BatimentsInternatViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour bâtiments internat."""

    permission_classes = [IsVieScolariteOrReadOnly]
    serializer_class = BatimentInternatSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    search_fields = ["nom"]
    ordering = ["nom"]

    def get_queryset(self):
        return BatimentInternat.objects.prefetch_related("chambres")

    @action(detail=True, methods=["get"])
    def chambres(self, request, pk=None):
        """Liste les chambres du bâtiment."""
        batiment = self.get_object()
        chambres = batiment.chambres.all().order_by("etage", "numero")
        serializer = ChambreListSerializer(chambres, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def statistiques(self, request, pk=None):
        """Statistiques du bâtiment."""
        batiment = self.get_object()
        chambres = batiment.chambres.all()
        today = timezone.now().date()

        capacite_totale = sum(c.capacite for c in chambres)
        occupants = (
            OccupantChambre.objects.filter(
                chambre__batiment=batiment,
                date_debut__lte=today,
            )
            .filter(Q(date_fin__isnull=True) | Q(date_fin__gte=today))
            .count()
        )

        return Response(
            {
                "batiment_id": batiment.id,
                "nb_chambres": chambres.count(),
                "capacite_totale": capacite_totale,
                "occupants": occupants,
                "places_disponibles": capacite_totale - occupants,
                "taux_occupation": (
                    round(occupants / capacite_totale * 100, 2)
                    if capacite_totale
                    else 0
                ),
            }
        )


class ChambresViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour chambres."""

    permission_classes = [IsVieScolariteOrReadOnly]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["batiment", "type", "etage"]
    ordering = ["batiment", "etage", "numero"]

    def get_queryset(self):
        return Chambre.objects.select_related("batiment")

    def get_serializer_class(self):
        if self.action == "list":
            return ChambreListSerializer
        return ChambreDetailSerializer

    @action(detail=True, methods=["get"])
    def occupants(self, request, pk=None):
        """Liste les occupants actuels de la chambre."""
        chambre = self.get_object()
        today = timezone.now().date()
        occupants = (
            chambre.occupants.filter(
                date_debut__lte=today,
            )
            .filter(Q(date_fin__isnull=True) | Q(date_fin__gte=today))
            .select_related("eleve__user", "eleve__classe")
        )
        serializer = OccupantChambreSerializer(occupants, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def disponibles(self, request):
        """Liste les chambres avec des places disponibles."""
        today = timezone.now().date()
        # Annoter avec le nombre d'occupants actuels
        chambres = Chambre.objects.annotate(
            nb_occupants_actuels=Count(
                "occupants",
                filter=Q(
                    occupants__date_debut__lte=today,
                )
                & (
                    Q(occupants__date_fin__isnull=True)
                    | Q(occupants__date_fin__gte=today)
                ),
            )
        ).filter(nb_occupants_actuels__lt=F("capacite"))
        serializer = ChambreListSerializer(chambres, many=True)
        return Response(serializer.data)


class OccupantsChambresViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour occupants."""

    permission_classes = [IsVieScolariteOrReadOnly]
    serializer_class = OccupantChambreSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["chambre", "eleve"]
    ordering = ["-date_debut"]

    def get_queryset(self):
        return OccupantChambre.objects.select_related(
            "chambre__batiment", "eleve__user", "eleve__classe"
        )

    @action(detail=True, methods=["post"])
    def liberer(self, request, pk=None):
        """Libère la place de l'occupant."""
        occupant = self.get_object()
        if occupant.date_fin:
            return Response(
                {"error": "Cette occupation est déjà terminée."}, status=400
            )

        occupant.date_fin = timezone.now().date()
        occupant.motif_fin = request.data.get("motif", "Libération")
        occupant.save(update_fields=["date_fin", "motif_fin"])
        return Response({"detail": "Chambre libérée.", "id": occupant.id})


class EtudesSurveilleesViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour études surveillées."""

    permission_classes = [IsVieScolariteOrReadOnly]
    serializer_class = EtudeSurveilleeSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["batiment", "date", "surveillant"]
    ordering = ["-date", "-heure_debut"]

    def get_queryset(self):
        return EtudeSurveillee.objects.select_related(
            "batiment", "surveillant"
        ).prefetch_related("eleves_presents")
