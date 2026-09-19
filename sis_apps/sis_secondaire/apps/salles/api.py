"""API views for salles (ViewSets DRF) - SIS Secondaire."""

from django.db.models import Count
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Salle
from .serializers import SalleDetailSerializer, SalleListSerializer


class IsAdminOrReadOnly(IsAuthenticated):
    """Permission: admin pour écriture, authentifié pour lecture."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        return request.user.is_staff


class SallesViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour salles."""

    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["etablissement", "type", "batiment", "accessible_pm"]
    search_fields = ["code", "nom", "batiment"]
    ordering_fields = ["nom", "batiment", "capacite"]
    ordering = ["batiment", "nom"]

    def get_queryset(self):
        return Salle.objects.select_related("etablissement")

    def get_serializer_class(self):
        if self.action == "list":
            return SalleListSerializer
        return SalleDetailSerializer

    @action(detail=False, methods=["get"])
    def par_type(self, request):
        """Statistiques par type de salle."""
        stats = self.get_queryset().values("type").annotate(count=Count("id"))
        return Response({s["type"]: s["count"] for s in stats})

    @action(detail=False, methods=["get"])
    def par_batiment(self, request):
        """Statistiques par bâtiment."""
        stats = self.get_queryset().values("batiment").annotate(count=Count("id"))
        return Response({s["batiment"] or "Non spécifié": s["count"] for s in stats})

    @action(detail=True, methods=["get"])
    def emploi_du_temps(self, request, pk=None):
        """Retourne l'emploi du temps de la salle."""
        salle = self.get_object()
        from apps.emplois_du_temps.models import Creneau
        from apps.emplois_du_temps.serializers import CreneauListSerializer

        creneaux = (
            Creneau.objects.filter(salle=salle, actif=True)
            .select_related("classe", "matiere", "enseignant__user")
            .order_by("jour", "heure_debut")
        )
        serializer = CreneauListSerializer(creneaux, many=True)
        return Response(serializer.data)
