"""API views for ECTS (ViewSets DRF) - SIS Supérieur."""

from django.db.models import Avg, Sum
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import BilanECTS
from .serializers import BilanECTSSerializer


class IsScolariteOrReadOnly(IsAuthenticated):
    """Permission: scolarité pour écriture."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        user = request.user
        return user.is_staff or getattr(user, "role", "") in (
            "scolarite",
            "responsable_formation",
            "doyen",
        )


class BilansECTSViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour bilans ECTS."""

    permission_classes = [IsScolariteOrReadOnly]
    serializer_class = BilanECTSSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = [
        "etudiant",
        "annee_universitaire",
        "inscription_admin__formation",
    ]
    ordering = ["-annee_universitaire__date_debut", "etudiant__user__last_name"]

    def get_queryset(self):
        return BilanECTS.objects.select_related(
            "etudiant__user", "annee_universitaire", "inscription_admin__formation"
        ).prefetch_related("ues_validees", "ues_compensees", "ues_echec")

    @action(detail=False, methods=["get"])
    def par_etudiant(self, request):
        """Bilans d'un étudiant."""
        etudiant_id = request.query_params.get("etudiant")
        if not etudiant_id:
            return Response({"error": "Paramètre etudiant requis."}, status=400)
        bilans = (
            self.get_queryset()
            .filter(etudiant_id=etudiant_id)
            .order_by("-annee_universitaire__date_debut")
        )
        serializer = self.get_serializer(bilans, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def statistiques(self, request):
        """Statistiques ECTS."""
        annee = request.query_params.get("annee")
        qs = self.get_queryset()
        if annee:
            qs = qs.filter(annee_universitaire_id=annee)

        stats = qs.aggregate(
            total_inscrits=Sum("credits_inscrits"),
            total_valides=Sum("credits_valides"),
            moyenne_generale=Avg("moyenne_ponderee"),
        )
        stats["nb_bilans"] = qs.count()
        stats["taux_validation_global"] = (
            (stats["total_valides"] / stats["total_inscrits"] * 100)
            if stats["total_inscrits"]
            else 0
        )
        return Response(stats)

    @action(detail=True, methods=["post"])
    def recalculer(self, request, pk=None):
        """Recalcule le bilan ECTS."""
        bilan = self.get_object()
        # Logique de recalcul basée sur les notes et décisions du jury
        # TODO: Implémenter le recalcul automatique
        from django.utils import timezone

        bilan.date_calcul = timezone.now()
        bilan.save(update_fields=["date_calcul"])
        return Response({"detail": "Bilan recalculé.", "id": bilan.id})
