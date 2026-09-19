"""API views for conseil de classe (ViewSets DRF) - SIS Secondaire."""

from django.db.models import Count
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import AppreciationConseil, ConseilClasse, DecisionConseil
from .serializers import (
    AppreciationConseilSerializer,
    ConseilClasseDetailSerializer,
    ConseilClasseListSerializer,
    DecisionConseilSerializer,
)


class IsDirectionOrReadOnly(IsAuthenticated):
    """Permission: direction pour écriture."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        user = request.user
        return user.is_staff or getattr(user, "role", "") in (
            "directeur",
            "proviseur",
            "principal",
            "cpe",
            "pp",
        )


class ConseilsClasseViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour conseils de classe."""

    permission_classes = [IsDirectionOrReadOnly]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["classe", "periode", "statut"]
    ordering = ["-date"]

    def get_queryset(self):
        return ConseilClasse.objects.select_related(
            "classe", "periode", "president", "secretaire"
        ).prefetch_related("participants", "decisions")

    def get_serializer_class(self):
        if self.action == "list":
            return ConseilClasseListSerializer
        return ConseilClasseDetailSerializer

    @action(detail=True, methods=["get"])
    def decisions(self, request, pk=None):
        """Liste les décisions du conseil."""
        conseil = self.get_object()
        decisions = conseil.decisions.select_related("eleve__user").order_by("rang")
        serializer = DecisionConseilSerializer(decisions, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def valider(self, request, pk=None):
        """Valide le conseil de classe."""
        conseil = self.get_object()
        if conseil.statut != "tenu":
            return Response({"error": "Le conseil doit d'abord être tenu."}, status=400)
        conseil.statut = "valide"
        conseil.save(update_fields=["statut"])
        return Response({"detail": "Conseil validé.", "id": conseil.id})

    @action(detail=True, methods=["post"])
    def tenir(self, request, pk=None):
        """Marque le conseil comme tenu."""
        conseil = self.get_object()
        if conseil.statut != "planifie":
            return Response({"error": "Statut invalide."}, status=400)
        conseil.statut = "tenu"
        conseil.save(update_fields=["statut"])
        return Response({"detail": "Conseil marqué comme tenu.", "id": conseil.id})

    @action(detail=True, methods=["get"])
    def statistiques(self, request, pk=None):
        """Statistiques du conseil."""
        conseil = self.get_object()
        decisions = conseil.decisions.all()
        stats = decisions.values("decision").annotate(count=Count("id"))
        return Response(
            {
                "nb_eleves": decisions.count(),
                "par_decision": {d["decision"]: d["count"] for d in stats},
            }
        )


class DecisionsConseilViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour décisions de conseil."""

    permission_classes = [IsDirectionOrReadOnly]
    serializer_class = DecisionConseilSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["conseil", "eleve", "decision"]
    ordering = ["rang"]

    def get_queryset(self):
        return DecisionConseil.objects.select_related("conseil", "eleve__user")


class AppreciationsConseilViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour appréciations."""

    permission_classes = [IsDirectionOrReadOnly]
    serializer_class = AppreciationConseilSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["conseil", "eleve"]

    def get_queryset(self):
        return AppreciationConseil.objects.select_related("conseil", "eleve__user")
