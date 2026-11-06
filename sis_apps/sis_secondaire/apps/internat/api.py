"""API views for internat (ViewSets DRF) - SIS Secondaire."""

from apps.eleves.models import Eleve
from django.db import transaction
from django.db.models import Count, F, Q
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
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


def _peak_room_occupation(room, start=None, end=None, exclude=None, from_date=None):
    occupants = OccupantChambre.objects.filter(chambre=room)
    if exclude is not None:
        occupants = occupants.exclude(pk=exclude)
    if from_date is not None:
        occupants = occupants.filter(Q(date_fin__isnull=True) | Q(date_fin__gte=from_date))
    if start is not None:
        occupants = occupants.filter(Q(date_fin__isnull=True) | Q(date_fin__gte=start))
        if end is not None:
            occupants = occupants.filter(date_debut__lte=end)

    intervals = list(occupants.values_list("date_debut", "date_fin"))
    if start is not None:
        intervals.append((start, end))
    events = []
    for begins, finishes in intervals:
        events.append((begins, 1))
        if finishes is not None:
            events.append((finishes, -1))
    # A stay ending on a date still occupies that date.
    events.sort(key=lambda event: (event[0], -event[1]))
    current = peak = 0
    for _, change in events:
        current += change
        peak = max(peak, current)
    return peak


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
                "taux_occupation": (round(occupants / capacite_totale * 100, 2) if capacite_totale else 0),
            }
        )


class ChambresViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour chambres."""

    permission_classes = [IsVieScolariteOrReadOnly]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["batiment", "type", "etage"]
    ordering = ["batiment", "etage", "numero"]

    def get_queryset(self):
        queryset = Chambre.objects.select_related("batiment")
        if self.action in ("update", "partial_update"):
            return queryset.select_for_update(of=("self",))
        return queryset

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    def perform_update(self, serializer):
        capacity = serializer.validated_data.get("capacite", serializer.instance.capacite)
        if capacity < serializer.instance.capacite and _peak_room_occupation(
            serializer.instance, from_date=timezone.localdate()
        ) > capacity:
            raise ValidationError({"capacite": "La capacité est inférieure aux occupations prévues."})
        serializer.save()

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
            .select_related("eleve__user", "eleve__classe_actuelle")
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
                & (Q(occupants__date_fin__isnull=True) | Q(occupants__date_fin__gte=today)),
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
        queryset = OccupantChambre.objects.filter(
            eleve__etablissement_id=self.request.tenant.pk
        ).select_related(
            "chambre__batiment", "eleve__user", "eleve__classe_actuelle"
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

    def _check_capacity(self, serializer):
        attrs = serializer.validated_data
        existing = serializer.instance
        room = attrs.get("chambre", existing.chambre if existing else None)
        pupil = attrs.get("eleve", existing.eleve if existing else None)
        start = attrs.get("date_debut", existing.date_debut if existing else None)
        end = attrs.get("date_fin", existing.date_fin if existing else None)
        room = Chambre.objects.select_for_update().get(pk=room.pk)
        Eleve.objects.select_for_update().get(pk=pupil.pk)
        other_stays = OccupantChambre.objects.filter(eleve=pupil).exclude(
            pk=existing.pk if existing else None
        ).filter(Q(date_fin__isnull=True) | Q(date_fin__gte=start))
        if end is not None:
            other_stays = other_stays.filter(date_debut__lte=end)
        if other_stays.exists():
            raise ValidationError({"eleve": "Cet élève occupe déjà une chambre pendant cette période."})
        if _peak_room_occupation(room, start, end, exclude=existing.pk if existing else None) > room.capacite:
            raise ValidationError({"chambre": "La chambre est complète pendant cette période."})

    def perform_create(self, serializer):
        self._check_capacity(serializer)
        serializer.save()

    def perform_update(self, serializer):
        self._check_capacity(serializer)
        serializer.save()

    @action(detail=True, methods=["post"])
    def liberer(self, request, pk=None):
        """Libère la place de l'occupant."""
        occupant = self.get_object()
        if occupant.date_fin:
            return Response({"error": "Cette occupation est déjà terminée."}, status=400)

        today = timezone.now().date()
        if occupant.date_debut > today:
            return Response({"error": "Cette occupation n'a pas encore commencé."}, status=400)

        occupant.date_fin = today
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
        return EtudeSurveillee.objects.select_related("batiment", "surveillant").prefetch_related("eleves_presents")
