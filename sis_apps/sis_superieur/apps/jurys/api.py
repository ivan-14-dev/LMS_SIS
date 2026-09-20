"""API views for jurys (ViewSets DRF) - SIS Supérieur."""

from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from sis_common.authorization import request_has_business_access

from .models import DecisionGlobale, DecisionJury, Deliberation, Jury
from .serializers import (
    DecisionGlobaleSerializer,
    DecisionJurySerializer,
    DeliberationSerializer,
    JuryDetailSerializer,
    JuryListSerializer,
)


class IsScolariteOrReadOnly(IsAuthenticated):
    """Permission: scolarité pour écriture."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        return request_has_business_access(
            request,
            "jurys.change_jury",
            ("scolarite", "responsable_formation", "doyen", "president_universite"),
            tenant_group_codes=("jury_manager_superieur",),
        )


class JurysViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour jurys."""

    permission_classes = [IsScolariteOrReadOnly]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["semestre", "formation", "statut"]
    ordering = ["-date"]

    def get_queryset(self):
        return Jury.objects.select_related(
            "semestre", "formation", "parcours", "president", "secretaire"
        ).prefetch_related("membres")

    def get_serializer_class(self):
        if self.action == "list":
            return JuryListSerializer
        return JuryDetailSerializer

    @action(detail=True, methods=["post"])
    def convoquer(self, request, pk=None):
        """Convoque le jury (envoi des convocations)."""
        jury = self.get_object()
        if jury.statut != "planifie":
            return Response({"error": "Jury déjà convoqué."}, status=400)
        jury.statut = "convoque"
        jury.save(update_fields=["statut"])
        # TODO: Envoyer les emails de convocation
        return Response({"detail": "Jury convoqué.", "id": jury.id})

    @action(detail=True, methods=["post"])
    def ouvrir_deliberation(self, request, pk=None):
        """Ouvre la délibération."""
        jury = self.get_object()
        if jury.statut not in ("convoque", "planifie"):
            return Response({"error": "Statut invalide."}, status=400)

        deliberation, created = Deliberation.objects.get_or_create(
            jury=jury, defaults={"date_ouverture": timezone.now()}
        )
        jury.statut = "reuni"
        jury.save(update_fields=["statut"])
        return Response(
            {"detail": "Délibération ouverte.", "deliberation_id": deliberation.id}
        )

    @action(detail=True, methods=["post"])
    def cloturer(self, request, pk=None):
        """Clôture le jury."""
        jury = self.get_object()
        if jury.statut != "delibere":
            return Response({"error": "Délibération non terminée."}, status=400)

        jury.statut = "cloture"
        jury.date_pv = timezone.now()
        jury.save(update_fields=["statut", "date_pv"])
        return Response({"detail": "Jury clôturé.", "id": jury.id})

    @action(detail=True, methods=["get"])
    def decisions(self, request, pk=None):
        """Liste les décisions du jury."""
        jury = self.get_object()
        if not hasattr(jury, "deliberation"):
            return Response({"error": "Pas de délibération."}, status=404)
        decisions = jury.deliberation.decisions.select_related("etudiant__user", "ue")
        serializer = DecisionJurySerializer(decisions, many=True)
        return Response(serializer.data)


class DeliberationsViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour délibérations."""

    permission_classes = [IsScolariteOrReadOnly]
    serializer_class = DeliberationSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["jury", "jury__formation"]
    ordering = ["-date_ouverture"]

    def get_queryset(self):
        return Deliberation.objects.select_related("jury__formation")

    @action(detail=True, methods=["post"])
    def cloturer(self, request, pk=None):
        """Clôture la délibération."""
        delib = self.get_object()
        if delib.date_cloture:
            return Response({"error": "Déjà clôturée."}, status=400)

        # Calculer les stats
        decisions = delib.decisions_globales.all()
        delib.nb_admis = decisions.filter(decision__startswith="admis").count()
        delib.nb_ajournes = decisions.filter(decision="ajourne").count()
        delib.nb_refuses = decisions.filter(decision="refuse").count()
        delib.date_cloture = timezone.now()
        delib.save()

        delib.jury.statut = "delibere"
        delib.jury.save(update_fields=["statut"])

        return Response({"detail": "Délibération clôturée.", "id": delib.id})


class DecisionsJuryViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour décisions par UE."""

    permission_classes = [IsScolariteOrReadOnly]
    serializer_class = DecisionJurySerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["deliberation", "etudiant", "ue", "decision"]
    ordering = ["etudiant__user__last_name"]

    def get_queryset(self):
        return DecisionJury.objects.select_related(
            "deliberation", "etudiant__user", "ue"
        )


class DecisionsGlobalesViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour décisions globales."""

    permission_classes = [IsScolariteOrReadOnly]
    serializer_class = DecisionGlobaleSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["deliberation", "etudiant", "decision"]
    ordering = ["etudiant__user__last_name"]

    def get_queryset(self):
        return DecisionGlobale.objects.select_related("deliberation", "etudiant__user")
