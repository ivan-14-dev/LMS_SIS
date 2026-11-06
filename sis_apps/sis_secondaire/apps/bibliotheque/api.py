"""API views for bibliotheque (ViewSets DRF) - SIS Secondaire."""

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from sis_common.authorization import is_current_tenant_user, request_has_business_access
from sis_common.hierarchy_attachments import PreserveOrganizationAttachmentsMixin

from .models import Emprunt, Exemplaire, Livre, Reservation
from .serializers import (
    EmpruntSerializer, ExemplaireSerializer, LivreDetailSerializer,
    LivreListSerializer, ReservationFulfilSerializer, ReservationSerializer,
)

ACTIVE_LOANS = ("en_cours", "en_retard")
ACTIVE_HOLDS = ("en_attente", "disponible")


def _can_manage_library(request):
    return request_has_business_access(
        request,
        "bibliotheque.change_livre",
        ("bibliothecaire", "documentaliste", "cdi", "directeur"),
        tenant_group_codes=("library_manager_secondary",),
    )


class IsBibliothecaireOrReadOnly(IsAuthenticated):
    """Permission: bibliothécaire/documentaliste pour écriture."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        return _can_manage_library(request)


class CanReserve(IsAuthenticated):
    def has_permission(self, request, view):
        return (
            super().has_permission(request, view)
            and is_current_tenant_user(request)
            and (view.action != "fulfil" or _can_manage_library(request))
        )


class LivresViewSet(PreserveOrganizationAttachmentsMixin, viewsets.ModelViewSet):
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
        copies = Exemplaire.objects.filter(etat__in=["neuf", "bon", "use"]).exclude(
            emprunts__statut__in=ACTIVE_LOANS
        )
        livres = self.get_queryset().filter(exemplaires__in=copies).distinct()
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

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        exemplaire = serializer.validated_data["exemplaire"]
        Livre.objects.select_for_update().get(pk=exemplaire.livre_id)
        exemplaire = Exemplaire.objects.select_for_update().get(pk=exemplaire.pk)
        if Reservation.objects.filter(
            livre_id=exemplaire.livre_id, statut__in=ACTIVE_HOLDS
        ).exists():
            raise ValidationError({"exemplaire": "Une réservation doit être honorée en premier."})
        if Emprunt.objects.filter(
            exemplaire=exemplaire, statut__in=ACTIVE_LOANS
        ).exists():
            raise ValidationError({"exemplaire": "Cet exemplaire est déjà emprunté."})
        if exemplaire.etat not in ("neuf", "bon", "use"):
            raise ValidationError({"exemplaire": "Cet exemplaire est indisponible."})
        return super().create(request, *args, **kwargs)

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


class ReservationsViewSet(viewsets.GenericViewSet):
    permission_classes = [CanReserve]
    serializer_class = ReservationSerializer

    def get_queryset(self):
        queryset = Reservation.objects.filter(
            utilisateur__etablissement_id=self.request.tenant.pk
        ).select_related("livre")
        if not _can_manage_library(self.request):
            queryset = queryset.filter(utilisateur=self.request.user)
        return queryset

    def list(self, request):
        return Response(self.get_serializer(self.get_queryset(), many=True).data)

    def retrieve(self, request, pk=None):
        return Response(self.get_serializer(self.get_object()).data)

    @transaction.atomic
    def create(self, request):
        if request.user.etablissement_id != request.tenant.pk:
            raise PermissionDenied("Un compte de l'établissement est requis.")
        if any(field in request.data for field in ("utilisateur", "statut", "emprunt")):
            raise ValidationError("Seul le livre peut être indiqué pour une réservation.")
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        livre = get_object_or_404(
            Livre.objects.select_for_update(), pk=serializer.validated_data["livre"].pk
        )
        if Reservation.objects.filter(
            livre=livre, utilisateur=request.user, statut__in=ACTIVE_HOLDS
        ).exists():
            raise ValidationError({"livre": "Vous avez déjà réservé ce livre."})
        if Emprunt.objects.filter(
            exemplaire__livre=livre, emprunteur=request.user, statut__in=ACTIVE_LOANS
        ).exists():
            raise ValidationError({"livre": "Vous empruntez déjà ce livre."})
        reservation = Reservation.objects.create(livre=livre, utilisateur=request.user)
        return Response(self.get_serializer(reservation).data, status=201)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def cancel(self, request, pk=None):
        reservation = self.get_object()
        Livre.objects.select_for_update().get(pk=reservation.livre_id)
        reservation = self.get_queryset().select_for_update(of=("self",)).get(pk=reservation.pk)
        if reservation.statut not in ACTIVE_HOLDS:
            raise ValidationError({"statut": "Cette réservation n'est plus active."})
        reservation.statut = "annulee"
        reservation.save(update_fields=["statut"])
        return Response(self.get_serializer(reservation).data)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def fulfil(self, request, pk=None):
        reservation = self.get_object()
        payload = ReservationFulfilSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        Livre.objects.select_for_update().get(pk=reservation.livre_id)
        reservation = self.get_queryset().select_for_update(of=("self",)).get(pk=reservation.pk)
        if reservation.statut not in ACTIVE_HOLDS:
            raise ValidationError({"statut": "Cette réservation n'est plus active."})
        first = Reservation.objects.filter(
            livre_id=reservation.livre_id, statut__in=ACTIVE_HOLDS
        ).order_by("date_reservation", "pk").first()
        if first.pk != reservation.pk:
            raise ValidationError({"statut": "Une réservation antérieure est prioritaire."})
        exemplaire = payload.validated_data["exemplaire"]
        if exemplaire.livre_id != reservation.livre_id:
            raise ValidationError({"exemplaire": "L'exemplaire n'appartient pas à ce livre."})
        exemplaire = Exemplaire.objects.select_for_update().get(pk=exemplaire.pk)
        if exemplaire.etat not in ("neuf", "bon", "use") or Emprunt.objects.filter(
            exemplaire=exemplaire, statut__in=ACTIVE_LOANS
        ).exists():
            raise ValidationError({"exemplaire": "Cet exemplaire est indisponible."})
        if Emprunt.objects.filter(
            exemplaire__livre_id=reservation.livre_id,
            emprunteur=reservation.utilisateur,
            statut__in=ACTIVE_LOANS,
        ).exists():
            raise ValidationError({"utilisateur": "Cet utilisateur emprunte déjà ce livre."})
        emprunt = Emprunt.objects.create(
            exemplaire=exemplaire,
            emprunteur=reservation.utilisateur,
            date_emprunt=timezone.localdate(),
            date_retour_prevue=payload.validated_data["date_retour_prevue"],
        )
        reservation.emprunt = emprunt
        reservation.statut = "honoree"
        reservation.save(update_fields=["emprunt", "statut"])
        return Response(self.get_serializer(reservation).data)
