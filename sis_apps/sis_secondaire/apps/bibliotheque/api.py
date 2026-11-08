"""API views for bibliotheque (ViewSets DRF) - SIS Secondaire."""

from datetime import timedelta

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import MethodNotAllowed, PermissionDenied, ValidationError
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from sis_common.authorization import is_current_tenant_user, request_has_business_access
from sis_common.digital_library import DigitalLibraryViewSetMixin, library_permission
from sis_common.hierarchy_attachments import PreserveOrganizationAttachmentsMixin

from .models import Emprunt, Exemplaire, Livre, Reservation
from .serializers import (
    EmpruntSerializer,
    ExemplaireSerializer,
    LivreDetailSerializer,
    LivreListSerializer,
    ReservationFulfilSerializer,
    ReservationSerializer,
)

ACTIVE_LOANS = ("en_cours", "en_retard", "perdu")
ACTIVE_HOLDS = ("en_attente", "disponible")


def _can_manage_library(request):
    return is_current_tenant_user(request) and request_has_business_access(
        request,
        "bibliotheque.change_livre",
        ("bibliothecaire", "documentaliste", "cdi", "directeur"),
        tenant_group_codes=("library_manager_secondary",),
    )


def _authorize_loan(request, emprunt):
    if not _can_manage_library(request) and not (
        emprunt.emprunteur_id == request.user.pk
        and library_permission(request, "bibliotheque.change_emprunt", emprunt.exemplaire.livre)
    ):
        raise PermissionDenied("Modification de cet emprunt non autorisée.")


class IsBibliothecaireOrReadOnly(IsAuthenticated):
    """Permission: bibliothécaire/documentaliste pour écriture."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if not is_current_tenant_user(request):
            return False
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        if view.basename == "emprunt" and view.action in ("create", "retourner", "renouveler"):
            permission = "add_emprunt" if view.action == "create" else "change_emprunt"
            if request.user.has_perm(f"bibliotheque.{permission}"):
                return True
        return _can_manage_library(request)


class IsTenantBibliothecaireOrReadOnly(IsBibliothecaireOrReadOnly):
    def has_permission(self, request, view):
        return is_current_tenant_user(request) and super().has_permission(request, view)


class CanReserve(IsAuthenticated):
    def has_permission(self, request, view):
        return (
            super().has_permission(request, view)
            and is_current_tenant_user(request)
            and (view.action != "fulfil" or _can_manage_library(request))
        )


class LivresViewSet(DigitalLibraryViewSetMixin, PreserveOrganizationAttachmentsMixin, viewsets.ModelViewSet):
    """ViewSet CRUD pour livres."""

    permission_classes = [IsBibliothecaireOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["categorie", "annee"]
    search_fields = ["titre", "auteurs", "isbn", "mots_cles"]
    ordering_fields = ["titre", "annee", "created_at"]
    ordering = ["titre"]

    def get_queryset(self):
        if not is_current_tenant_user(self.request):
            raise PermissionDenied("Compte hors établissement.")
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
        serializer = ExemplaireSerializer(exemplaires, many=True, context=self.get_serializer_context())
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def disponibles(self, request):
        """Liste les livres avec au moins un exemplaire disponible."""
        copies = Exemplaire.objects.filter(etat__in=["neuf", "bon", "use"]).exclude(emprunts__statut__in=ACTIVE_LOANS)
        livres = self.get_queryset().filter(exemplaires__in=copies).distinct()
        serializer = LivreListSerializer(livres, many=True, context=self.get_serializer_context())
        return Response([livre for livre in serializer.data if livre["disponibles"] > 0])

    @transaction.atomic
    def perform_destroy(self, instance):
        if not library_permission(self.request, "bibliotheque.change_livre", instance):
            raise PermissionDenied("Le droit explicite de modifier ce livre est requis.")
        Livre.objects.select_for_update().get(pk=instance.pk)
        if instance.reservations.exists() or Emprunt.objects.filter(exemplaire__livre=instance).exists():
            raise ValidationError("Le titre possède un historique de réservations ou d'emprunts.")
        instance.delete()


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

    @transaction.atomic
    def perform_update(self, serializer):
        instance = Exemplaire.objects.select_for_update().get(pk=serializer.instance.pk)
        serializer.instance = instance
        livre = serializer.validated_data.get("livre")
        if livre and livre.pk != instance.livre_id and instance.emprunts.exists():
            raise ValidationError({"livre": "Un exemplaire emprunté ne peut changer de titre."})
        serializer.save()

    @transaction.atomic
    def perform_destroy(self, instance):
        Livre.objects.select_for_update().get(pk=instance.livre_id)
        instance = Exemplaire.objects.select_for_update().get(pk=instance.pk)
        if instance.emprunts.exists():
            raise ValidationError("L'exemplaire possède un historique d'emprunts.")
        instance.delete()


class EmpruntsViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour emprunts."""

    permission_classes = [IsTenantBibliothecaireOrReadOnly]
    serializer_class = EmpruntSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["exemplaire", "emprunteur", "statut"]
    ordering = ["-date_emprunt"]

    def get_queryset(self):
        queryset = Emprunt.objects.filter(
            emprunteur__etablissement_id=self.request.tenant.pk
        ).select_related("exemplaire__livre", "emprunteur")
        if not _can_manage_library(self.request):
            queryset = queryset.filter(emprunteur=self.request.user)
        return queryset

    @transaction.atomic
    def perform_create(self, serializer):
        if set(serializer.validated_data) - {"exemplaire", "emprunteur", "date_emprunt", "date_retour_prevue"}:
            raise ValidationError("Le statut et les résultats de l'emprunt ne sont pas modifiables.")
        exemplaire = serializer.validated_data["exemplaire"]
        livre = Livre.objects.select_for_update().get(pk=exemplaire.livre_id)
        exemplaire = Exemplaire.objects.select_for_update().get(pk=exemplaire.pk)
        emprunteur = serializer.validated_data.get("emprunteur", self.request.user)
        manager = _can_manage_library(self.request)
        if not manager and not (
            emprunteur.pk == self.request.user.pk
            and library_permission(self.request, "bibliotheque.add_emprunt", livre)
        ):
            raise PermissionDenied("Seul un prêt personnel explicitement autorisé peut être créé.")
        reservations = Reservation.objects.filter(livre=livre, statut__in=ACTIVE_HOLDS)
        own_reservation = reservations.filter(utilisateur=emprunteur).order_by("date_reservation", "pk").first()
        first = reservations.order_by("date_reservation", "pk").first()
        if first and (own_reservation is None or own_reservation.pk != first.pk):
            raise ValidationError({"exemplaire": "Une réservation doit être honorée en premier."})
        if Emprunt.objects.filter(exemplaire=exemplaire, statut__in=ACTIVE_LOANS).exists():
            raise ValidationError({"exemplaire": "Cet exemplaire est déjà emprunté."})
        if exemplaire.livre_id != livre.pk or exemplaire.etat not in ("neuf", "bon", "use"):
            raise ValidationError({"exemplaire": "Cet exemplaire est indisponible."})
        today = timezone.localdate()
        start = serializer.validated_data.get("date_emprunt", today)
        end = serializer.validated_data.get("date_retour_prevue", today + timedelta(days=14))
        if not manager and (start != today or end != today + timedelta(days=14)):
            raise ValidationError("Les dates d'un prêt personnel sont fixées par la bibliothèque.")
        if end <= start or end <= today or start > today:
            raise ValidationError("Dates d'emprunt incohérentes.")
        loan = serializer.save(emprunteur=emprunteur, date_emprunt=start, date_retour_prevue=end)
        if own_reservation:
            own_reservation.statut = "honoree"
            own_reservation.emprunt = loan
            own_reservation.save(update_fields=["statut", "emprunt"])

    def update(self, request, *args, **kwargs):
        raise MethodNotAllowed(request.method, detail="Utiliser les actions retourner et renouveler.")

    def destroy(self, request, *args, **kwargs):
        raise MethodNotAllowed(request.method, detail="Un emprunt ne peut être supprimé.")

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
    @transaction.atomic
    def retourner(self, request, pk=None):
        """Enregistre le retour d'un emprunt."""
        livre_id = get_object_or_404(self.get_queryset().values_list("exemplaire__livre_id", flat=True), pk=pk)
        Livre.objects.select_for_update().get(pk=livre_id)
        emprunt = get_object_or_404(self.get_queryset().select_for_update(of=("self",)), pk=pk)
        _authorize_loan(request, emprunt)
        if emprunt.statut not in ("en_cours", "en_retard"):
            return Response({"error": "Emprunt non en cours."}, status=400)

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
    @transaction.atomic
    def renouveler(self, request, pk=None):
        """Renouvelle l'emprunt."""
        livre_id = get_object_or_404(self.get_queryset().values_list("exemplaire__livre_id", flat=True), pk=pk)
        Livre.objects.select_for_update().get(pk=livre_id)
        emprunt = get_object_or_404(self.get_queryset().select_for_update(of=("self",)), pk=pk)
        _authorize_loan(request, emprunt)
        if Reservation.objects.filter(livre_id=livre_id, statut__in=ACTIVE_HOLDS).exists():
            raise ValidationError("Une réservation en attente interdit le renouvellement.")
        if emprunt.statut != "en_cours":
            return Response({"error": "Emprunt non en cours."}, status=400)
        if emprunt.nb_renouvellements >= 2:
            return Response({"error": "Maximum 2 renouvellements."}, status=400)

        # Prolonger de 14 jours
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
        if (
            exemplaire.livre_id != reservation.livre_id
            or exemplaire.etat not in ("neuf", "bon", "use")
            or Emprunt.objects.filter(exemplaire=exemplaire, statut__in=ACTIVE_LOANS).exists()
        ):
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
