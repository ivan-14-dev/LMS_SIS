"""API views for mobilite internationale (ViewSets DRF) - SIS Supérieur."""

from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import AccordEtudes, CandidatureMobilite, ProgrammeMobilite
from .serializers import (
    AccordEtudesSerializer,
    CandidatureMobiliteDetailSerializer,
    CandidatureMobiliteListSerializer,
    ProgrammeMobiliteDetailSerializer,
    ProgrammeMobiliteListSerializer,
)


class IsRelationsInternationalesOrReadOnly(IsAuthenticated):
    """Permission: relations internationales pour écriture."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        user = request.user
        return user.is_staff or getattr(user, "role", "") in (
            "relations_internationales",
            "scolarite",
            "doyen",
            "vice_president",
        )


class ProgrammesMobiliteViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour programmes de mobilité."""

    permission_classes = [IsRelationsInternationalesOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["formation", "type", "pays", "actif", "annee_universitaire"]
    search_fields = ["nom", "universite_accueil", "pays"]
    ordering = ["-date_limite_candidature"]

    def get_queryset(self):
        return ProgrammeMobilite.objects.select_related(
            "formation", "annee_universitaire"
        ).prefetch_related("candidatures")

    def get_serializer_class(self):
        if self.action == "list":
            return ProgrammeMobiliteListSerializer
        return ProgrammeMobiliteDetailSerializer

    @action(detail=False, methods=["get"])
    def ouverts(self, request):
        """Liste les programmes avec candidatures ouvertes."""
        today = timezone.now().date()
        programmes = self.get_queryset().filter(
            actif=True, date_limite_candidature__gte=today
        )
        serializer = ProgrammeMobiliteListSerializer(programmes, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def candidatures(self, request, pk=None):
        """Liste les candidatures du programme."""
        programme = self.get_object()
        candidatures = programme.candidatures.select_related("etudiant__user").order_by(
            "-date_soumission"
        )
        serializer = CandidatureMobiliteListSerializer(candidatures, many=True)
        return Response(serializer.data)


class CandidaturesMobiliteViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour candidatures."""

    permission_classes = [IsRelationsInternationalesOrReadOnly]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["programme", "etudiant", "statut"]
    ordering = ["-date_soumission"]

    def get_queryset(self):
        return CandidatureMobilite.objects.select_related(
            "etudiant__user", "programme", "decision_par"
        )

    def get_serializer_class(self):
        if self.action == "list":
            return CandidatureMobiliteListSerializer
        return CandidatureMobiliteDetailSerializer

    @action(detail=True, methods=["post"])
    def soumettre(self, request, pk=None):
        """Soumet la candidature."""
        candidature = self.get_object()
        if candidature.statut != "brouillon":
            return Response({"error": "Déjà soumise."}, status=400)
        candidature.statut = "soumise"
        candidature.date_soumission = timezone.now()
        candidature.save(update_fields=["statut", "date_soumission"])
        return Response({"detail": "Candidature soumise.", "id": candidature.id})

    @action(detail=True, methods=["post"])
    def decider(self, request, pk=None):
        """Décision sur la candidature."""
        candidature = self.get_object()
        decision = request.data.get("decision")  # acceptee, refusee
        if decision not in ("acceptee", "refusee", "preselectionne"):
            return Response({"error": "Décision invalide."}, status=400)

        candidature.statut = decision
        candidature.decision_par = request.user
        if decision == "refusee":
            candidature.motif_refus = request.data.get("motif", "")
        candidature.save(update_fields=["statut", "decision_par", "motif_refus"])
        return Response({"detail": f"Candidature {decision}.", "id": candidature.id})


class AccordsEtudesViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour accords d'études."""

    permission_classes = [IsRelationsInternationalesOrReadOnly]
    serializer_class = AccordEtudesSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["candidature", "statut"]

    def get_queryset(self):
        return AccordEtudes.objects.select_related(
            "candidature__etudiant__user", "candidature__programme"
        )

    @action(detail=True, methods=["post"])
    def valider_origine(self, request, pk=None):
        """Validation par l'établissement d'origine."""
        accord = self.get_object()
        accord.statut = "valide_local"
        accord.date_validation_origine = timezone.now()
        accord.save(update_fields=["statut", "date_validation_origine"])
        return Response({"detail": "Validé par l'origine.", "id": accord.id})

    @action(detail=True, methods=["post"])
    def valider_accueil(self, request, pk=None):
        """Validation par l'université d'accueil."""
        accord = self.get_object()
        accord.statut = "valide_accueil"
        accord.date_validation_accueil = timezone.now()
        accord.save(update_fields=["statut", "date_validation_accueil"])
        return Response({"detail": "Validé par l'accueil.", "id": accord.id})
