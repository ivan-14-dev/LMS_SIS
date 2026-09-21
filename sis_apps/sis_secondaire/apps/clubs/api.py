"""API views for clubs (ViewSets DRF) - SIS Secondaire."""

from django.db.models import Count
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from sis_common.authorization import request_has_business_access

from .models import Club, MembreClub, SeanceClub
from .serializers import ClubDetailSerializer, ClubListSerializer, MembreClubSerializer, SeanceClubSerializer


class IsVieScolariteOrReadOnly(IsAuthenticated):
    """Permission: vie scolaire pour écriture."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        return request_has_business_access(
            request,
            "clubs.change_club",
            ("vie_scolaire", "cpe", "directeur", "responsable_club"),
            tenant_group_codes=("club_manager_secondary",),
        )


class ClubsViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour clubs."""

    permission_classes = [IsVieScolariteOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["type", "actif", "responsable"]
    search_fields = ["nom", "description"]
    ordering = ["nom"]

    def get_queryset(self):
        return Club.objects.select_related("responsable").prefetch_related("membres")

    def get_serializer_class(self):
        if self.action == "list":
            return ClubListSerializer
        return ClubDetailSerializer

    @action(detail=True, methods=["get"])
    def membres(self, request, pk=None):
        """Liste les membres du club."""
        club = self.get_object()
        membres = (
            club.membres.filter(statut="actif")
            .select_related("eleve__user", "eleve__classe")
            .order_by("eleve__user__last_name")
        )
        serializer = MembreClubSerializer(membres, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def seances(self, request, pk=None):
        """Liste les séances du club."""
        club = self.get_object()
        seances = club.seances.all().order_by("-date")[:20]
        serializer = SeanceClubSerializer(seances, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def statistiques(self, request):
        """Statistiques des clubs."""
        stats = Club.objects.filter(actif=True).aggregate(
            total=Count("id"),
        )
        by_type = (
            Club.objects.filter(actif=True).values("type").annotate(count=Count("id"))
        )
        stats["par_type"] = {t["type"]: t["count"] for t in by_type}
        stats["total_membres"] = MembreClub.objects.filter(statut="actif").count()
        return Response(stats)


class MembresClubViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour membres de club."""

    permission_classes = [IsVieScolariteOrReadOnly]
    serializer_class = MembreClubSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["club", "eleve", "statut"]
    ordering = ["eleve__user__last_name"]

    def get_queryset(self):
        return MembreClub.objects.select_related("club", "eleve__user", "eleve__classe")

    @action(detail=True, methods=["post"])
    def suspendre(self, request, pk=None):
        """Suspend un membre."""
        membre = self.get_object()
        membre.statut = "suspendu"
        membre.save(update_fields=["statut"])
        return Response({"detail": "Membre suspendu.", "id": membre.id})

    @action(detail=True, methods=["post"])
    def reactiver(self, request, pk=None):
        """Réactive un membre."""
        membre = self.get_object()
        membre.statut = "actif"
        membre.save(update_fields=["statut"])
        return Response({"detail": "Membre réactivé.", "id": membre.id})


class SeancesClubViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour séances de club."""

    permission_classes = [IsVieScolariteOrReadOnly]
    serializer_class = SeanceClubSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["club", "date"]
    ordering = ["-date"]

    def get_queryset(self):
        return SeanceClub.objects.select_related("club").prefetch_related("presents")
