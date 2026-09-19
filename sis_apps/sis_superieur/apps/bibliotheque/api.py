"""API views for bibliotheque (ViewSets DRF) - SIS Supérieur."""

from datetime import timedelta

from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Emprunt, Exemplaire, Livre, Reservation
from .serializers import (
    EmpruntSerializer,
    ExemplaireSerializer,
    LivreDetailSerializer,
    LivreListSerializer,
    ReservationSerializer,
)


class IsBibliothecaireOrReadOnly(IsAuthenticated):
    """Permission: bibliothécaire pour écriture, authentifié pour lecture."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        user = request.user
        return user.is_staff or getattr(user, "role", "") in (
            "bibliothecaire",
            "responsable_bibliotheque",
        )


class LivresViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour livres."""

    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["categorie", "langue", "annee_publication"]
    search_fields = ["titre", "auteurs", "isbn", "mots_cles", "resume"]
    ordering_fields = ["titre", "auteurs", "annee_publication"]
    ordering = ["titre"]

    def get_queryset(self):
        return Livre.objects.all()

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

    @action(detail=True, methods=["post"])
    def reserver(self, request, pk=None):
        """Réserve le livre."""
        livre = self.get_object()
        user = request.user

        # Vérifier si déjà réservé
        if Reservation.objects.filter(
            livre=livre, utilisateur=user, statut="en_attente"
        ).exists():
            return Response({"error": "Vous avez déjà réservé ce livre."}, status=400)

        reservation = Reservation.objects.create(
            livre=livre,
            utilisateur=user,
        )
        return Response(
            {
                "detail": "Réservation enregistrée.",
                "id": reservation.id,
                "position": Reservation.objects.filter(
                    livre=livre, statut="en_attente"
                ).count(),
            }
        )


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
        qs = Emprunt.objects.select_related("exemplaire__livre", "emprunteur")
        user = self.request.user
        # Un utilisateur ne voit que ses propres emprunts (sauf bibliothécaire)
        if not user.is_staff and getattr(user, "role", "") not in (
            "bibliothecaire",
            "responsable_bibliotheque",
        ):
            qs = qs.filter(emprunteur=user)
        return qs

    def perform_create(self, serializer):
        # Définir la date de retour prévue (21 jours par défaut)
        if not serializer.validated_data.get("date_retour_prevue"):
            serializer.validated_data["date_retour_prevue"] = (
                timezone.now().date() + timedelta(days=21)
            )
        serializer.save()

    @action(detail=True, methods=["post"])
    def rendre(self, request, pk=None):
        """Rend un emprunt."""
        emprunt = self.get_object()
        if emprunt.statut != "en_cours":
            return Response({"error": "Cet emprunt n'est pas en cours."}, status=400)

        emprunt.statut = "rendu"
        emprunt.date_retour_reelle = timezone.now().date()

        # Calculer la pénalité si retard
        if emprunt.date_retour_reelle > emprunt.date_retour_prevue:
            jours_retard = (
                emprunt.date_retour_reelle - emprunt.date_retour_prevue
            ).days
            emprunt.penalite = jours_retard * 0.50  # 0.50€ par jour

        emprunt.save(update_fields=["statut", "date_retour_reelle", "penalite"])
        return Response(
            {
                "detail": "Livre rendu.",
                "id": emprunt.id,
                "penalite": float(emprunt.penalite),
            }
        )

    @action(detail=True, methods=["post"])
    def renouveler(self, request, pk=None):
        """Renouvelle un emprunt."""
        emprunt = self.get_object()
        if emprunt.statut != "en_cours":
            return Response({"error": "Cet emprunt n'est pas en cours."}, status=400)
        if emprunt.nb_renouvellements >= 2:
            return Response(
                {"error": "Limite de renouvellements atteinte."}, status=400
            )

        emprunt.date_retour_prevue += timedelta(days=14)
        emprunt.nb_renouvellements += 1
        emprunt.statut = "renouvele"
        emprunt.save(
            update_fields=["date_retour_prevue", "nb_renouvellements", "statut"]
        )
        return Response(
            {
                "detail": "Emprunt renouvelé.",
                "id": emprunt.id,
                "nouvelle_date_retour": emprunt.date_retour_prevue,
            }
        )

    @action(detail=False, methods=["get"])
    def en_retard(self, request):
        """Liste les emprunts en retard."""
        today = timezone.now().date()
        qs = self.get_queryset().filter(statut="en_cours", date_retour_prevue__lt=today)
        serializer = EmpruntSerializer(qs, many=True)
        return Response(serializer.data)


class ReservationsViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour réservations."""

    permission_classes = [IsAuthenticated]
    serializer_class = ReservationSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["livre", "utilisateur", "statut"]
    ordering = ["date_reservation"]

    def get_queryset(self):
        qs = Reservation.objects.select_related("livre", "utilisateur")
        user = self.request.user
        # Un utilisateur ne voit que ses propres réservations (sauf bibliothécaire)
        if not user.is_staff and getattr(user, "role", "") not in (
            "bibliothecaire",
            "responsable_bibliotheque",
        ):
            qs = qs.filter(utilisateur=user)
        return qs

    @action(detail=True, methods=["post"])
    def annuler(self, request, pk=None):
        """Annule une réservation."""
        reservation = self.get_object()
        if reservation.statut != "en_attente":
            return Response(
                {"error": "Cette réservation ne peut pas être annulée."}, status=400
            )
        reservation.statut = "annulee"
        reservation.save(update_fields=["statut"])
        return Response({"detail": "Réservation annulée.", "id": reservation.id})
