"""API views for bibliotheque (ViewSets DRF) - SIS Secondaire."""

from django.db.models import Count, Q
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from sis_common.authorization import request_has_business_access

from .models import Emprunt, Exemplaire, Livre
from .serializers import EmpruntSerializer, ExemplaireSerializer, LivreDetailSerializer, LivreListSerializer


class IsBibliothecaireOrReadOnly(IsAuthenticated):
    """Permission: bibliothécaire/documentaliste pour écriture."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        return request_has_business_access(
            request,
            "bibliotheque.change_livre",
            ("bibliothecaire", "documentaliste", "cdi", "directeur"),
            tenant_group_codes=("library_manager_secondary",),
        )


class LivresViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour livres."""

    permission_classes = [IsBibliothecaireOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["categorie", "annee"]
    search_fields = ["titre", "auteurs", "isbn", "mots_cles"]
    ordering_fields = ["titre", "annee", "created_at"]
    ordering = ["titre"]

    def get_queryset(self):
        return Livre.objects.prefetch_related("exemplaires")

    def get_serializer_class(self):
        if self.action == "list":
            return LivreListSerializer
        return LivreDetailSerializer

    @action(detail=True, methods=["get"])
    def exemplaires(self, request, pk=None):
        """Liste les exemplaires du livre."""
        livre = self.get_object()
        exemplaires = livre.exemplaires.all().order_by("code_barre")
        serializer = ExemplaireSerializer(exemplaires, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def disponibles(self, request):
        """Liste les livres avec au moins un exemplaire disponible."""
        livres = (
            self.get_queryset()
            .annotate(
                nb_dispo=Count(
                    "exemplaires",
                    filter=Q(exemplaires__etat__in=["neuf", "bon", "use"])
                    & ~Q(exemplaires__emprunts__statut="en_cours"),
                )
            )
            .filter(nb_dispo__gt=0)
        )
        serializer = LivreListSerializer(livres, many=True)
        return Response(serializer.data)


class ExemplairesViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour exemplaires."""

    permission_classes = [IsBibliothecaireOrReadOnly]
    serializer_class = ExemplaireSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["livre", "etat"]
    search_fields = ["code_barre", "livre__titre"]
    ordering = ["code_barre"]

    def get_queryset(self):
        return Exemplaire.objects.select_related("livre")


class EmpruntsViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour emprunts."""

    permission_classes = [IsBibliothecaireOrReadOnly]
    serializer_class = EmpruntSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["exemplaire", "emprunteur", "statut"]
    ordering = ["-date_emprunt"]

    def get_queryset(self):
        return Emprunt.objects.select_related("exemplaire__livre", "emprunteur")

    @action(detail=False, methods=["get"])
    def en_retard(self, request):
        """Liste les emprunts en retard."""
        today = timezone.now().date()
        emprunts = self.get_queryset().filter(
            statut="en_cours", date_retour_prevue__lt=today
        )
        serializer = EmpruntSerializer(emprunts, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def retourner(self, request, pk=None):
        """Enregistre le retour d'un emprunt."""
        emprunt = self.get_object()
        if emprunt.statut == "rendu":
            return Response({"error": "Déjà rendu."}, status=400)

        today = timezone.now().date()
        emprunt.date_retour_reelle = today
        emprunt.statut = "rendu"

        # Calculer la pénalité si en retard
        if today > emprunt.date_retour_prevue:
            jours_retard = (today - emprunt.date_retour_prevue).days
            emprunt.penalite = jours_retard * 0.50  # 0.50€ par jour de retard

        emprunt.save(update_fields=["date_retour_reelle", "statut", "penalite"])
        return Response({"detail": "Retour enregistré.", "id": emprunt.id})

    @action(detail=True, methods=["post"])
    def renouveler(self, request, pk=None):
        """Renouvelle l'emprunt."""
        emprunt = self.get_object()
        if emprunt.statut != "en_cours":
            return Response({"error": "Emprunt non en cours."}, status=400)
        if emprunt.nb_renouvellements >= 2:
            return Response({"error": "Maximum 2 renouvellements."}, status=400)

        # Prolonger de 14 jours
        from datetime import timedelta

        emprunt.date_retour_prevue += timedelta(days=14)
        emprunt.nb_renouvellements += 1
        emprunt.save(update_fields=["date_retour_prevue", "nb_renouvellements"])
        return Response(
            {
                "detail": "Emprunt renouvelé.",
                "nouvelle_date": emprunt.date_retour_prevue,
            }
        )
