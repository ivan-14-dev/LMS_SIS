"""API views for bibliotheque (ViewSets DRF) - SIS Supérieur."""

from datetime import timedelta

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import MethodNotAllowed, PermissionDenied, ValidationError
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from sis_common.authorization import is_current_tenant_user, request_has_business_access
from sis_common.hierarchy_attachments import PreserveOrganizationAttachmentsMixin

from .models import Emprunt, Exemplaire, Livre, Reservation
from .serializers import (
    EmpruntSerializer,
    ExemplaireSerializer,
    LivreDetailSerializer,
    LivreListSerializer,
    ReservationClaimSerializer,
    ReservationRemiseSerializer,
    ReservationSerializer,
    STATUTS_EMPRUNT_ACTIF,
    STATUTS_EMPRUNT_OCCUPANT,
    exemplaires_disponibles,
    exemplaires_empruntables,
)

STATUTS_RESERVATION_ACTIVE = ("en_attente", "disponible")


def _local_user(request):
    if not is_current_tenant_user(request):
        raise PermissionDenied("Compte hors établissement.")


def _bibliothecaire(request):
    _local_user(request)
    if not (
        request.user.is_staff
        or request_has_business_access(
            request, "bibliotheque.change_livre", ("bibliothecaire", "responsable_bibliotheque")
        )
    ):
        raise PermissionDenied("Bibliothécaire requis.")


def _reclamer(livre, request):
    _local_user(request)
    livre = Livre.objects.select_for_update().get(pk=livre.pk)
    if not livre.exemplaires.exclude(etat__in=("perdu", "détérioré")).exists():
        raise ValidationError({"livre": "Aucun exemplaire empruntable."})
    if Reservation.objects.filter(
        livre=livre, utilisateur=request.user, statut__in=STATUTS_RESERVATION_ACTIVE
    ).exists():
        raise ValidationError({"livre": "Réservation déjà active."})
    if Emprunt.objects.filter(
        exemplaire__livre=livre, emprunteur=request.user, statut__in=STATUTS_EMPRUNT_OCCUPANT
    ).exists():
        raise ValidationError({"livre": "Livre déjà emprunté."})
    reservations = Reservation.objects.filter(livre=livre, statut__in=STATUTS_RESERVATION_ACTIVE)
    if exemplaires_disponibles(livre) > reservations.count():
        raise ValidationError({"livre": "Un exemplaire est disponible pour un emprunt direct."})
    reservation = Reservation.objects.create(livre=livre, utilisateur=request.user)
    return Response(
        {"detail": "Réservation enregistrée.", "id": reservation.pk, "position": reservations.count()},
        status=status.HTTP_201_CREATED,
    )


class IsBibliothecaireOrReadOnly(IsAuthenticated):
    """Permission: bibliothécaire pour écriture, authentifié pour lecture."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        return is_current_tenant_user(request) and (
            request.user.is_staff
            or request_has_business_access(
                request, "bibliotheque.change_livre", ("bibliothecaire", "responsable_bibliotheque")
            )
        )


class LivresViewSet(PreserveOrganizationAttachmentsMixin, viewsets.ModelViewSet):
    """ViewSet CRUD pour livres."""

    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["categorie", "langue", "annee_publication"]
    search_fields = ["titre", "auteurs", "isbn", "mots_cles", "resume"]
    ordering_fields = ["titre", "auteurs", "annee_publication"]
    ordering = ["titre"]

    def get_permissions(self):
        if self.action != "reserver":
            return [IsBibliothecaireOrReadOnly()]
        return super().get_permissions()

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
    @transaction.atomic
    def reserver(self, request, pk=None):
        """Ajoute le demandeur à la file d'attente d'un titre indisponible."""
        _local_user(request)
        if request.data:
            raise ValidationError("Aucune identité ni statut ne peut être fourni.")
        livre = self.get_object()
        return _reclamer(livre, request)

    @transaction.atomic
    def perform_destroy(self, instance):
        Livre.objects.select_for_update().get(pk=instance.pk)
        if instance.reservations.exists():
            raise ValidationError("Le titre possède un historique de réservations.")
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
        nouveau_livre = serializer.validated_data.get("livre")
        if nouveau_livre and nouveau_livre.pk != instance.livre_id and instance.emprunts.exists():
            raise ValidationError({"livre": "Un exemplaire emprunté ne peut changer de titre."})
        serializer.save()


class EmpruntsViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD pour emprunts."""

    permission_classes = [IsBibliothecaireOrReadOnly]
    serializer_class = EmpruntSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["exemplaire", "emprunteur", "statut"]
    ordering = ["-date_emprunt"]

    def get_queryset(self):
        qs = Emprunt.objects.filter(
            emprunteur__etablissement_id=self.request.tenant.pk
        ).select_related("exemplaire__livre", "emprunteur")
        user = self.request.user
        # Un utilisateur ne voit que ses propres emprunts (sauf bibliothécaire)
        if not (
            user.is_staff or request_has_business_access(
                self.request, "bibliotheque.change_livre", ("bibliothecaire", "responsable_bibliotheque")
            )
        ):
            qs = qs.filter(emprunteur=user)
        if self.action in ("rendre", "renouveler"):
            qs = qs.select_for_update(of=("self",))
        return qs

    @transaction.atomic
    def perform_create(self, serializer):
        _bibliothecaire(self.request)
        if set(serializer.validated_data) - {
            "exemplaire", "emprunteur", "date_emprunt", "date_retour_prevue"
        }:
            raise ValidationError("Le statut et les résultats de l'emprunt ne sont pas modifiables.")
        exemplaire = serializer.validated_data["exemplaire"]
        emprunteur = serializer.validated_data["emprunteur"]
        if emprunteur.etablissement_id != self.request.tenant.pk:
            raise ValidationError({"emprunteur": "Compte hors établissement."})
        livre = Livre.objects.select_for_update().get(pk=exemplaire.livre_id)
        exemplaire = Exemplaire.objects.select_for_update().get(pk=exemplaire.pk)
        if exemplaire.livre_id != livre.pk or exemplaire.etat in ("perdu", "détérioré"):
            raise ValidationError({"exemplaire": "Exemplaire indisponible."})
        if Emprunt.objects.filter(exemplaire=exemplaire, statut__in=STATUTS_EMPRUNT_OCCUPANT).exists():
            raise ValidationError({"exemplaire": "Exemplaire déjà emprunté."})
        reservations = Reservation.objects.filter(livre=livre, statut__in=STATUTS_RESERVATION_ACTIVE)
        if reservations.filter(utilisateur=emprunteur).exists() or (
            exemplaires_disponibles(livre) <= reservations.count()
        ):
            raise ValidationError({"exemplaire": "Exemplaire réservé ; utiliser la remise de réservation."})
        # Définir la date de retour prévue (21 jours par défaut)
        if not serializer.validated_data.get("date_retour_prevue"):
            serializer.validated_data["date_retour_prevue"] = (
                timezone.now().date() + timedelta(days=21)
            )
        serializer.save()

    def update(self, request, *args, **kwargs):
        raise MethodNotAllowed(request.method, detail="Utiliser les actions rendre et renouveler.")

    def destroy(self, request, *args, **kwargs):
        raise MethodNotAllowed(request.method, detail="Un emprunt ne peut être supprimé.")

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def rendre(self, request, pk=None):
        """Rend un emprunt et indique si l'exemplaire est empruntable sans réservation."""
        _bibliothecaire(request)
        livre_id = get_object_or_404(
            Emprunt.objects.values_list("exemplaire__livre_id", flat=True), pk=pk
        )
        Livre.objects.select_for_update().get(pk=livre_id)
        emprunt = self.get_object()
        if emprunt.statut not in (*STATUTS_EMPRUNT_ACTIF, "en_retard"):
            return Response({"error": "Cet emprunt n'est pas en cours."}, status=400)

        exemplaire = Exemplaire.objects.select_for_update().get(pk=emprunt.exemplaire_id)
        emprunt.statut = "rendu"
        emprunt.date_retour_reelle = timezone.now().date()

        # Calculer la pénalité si retard
        if emprunt.date_retour_reelle > emprunt.date_retour_prevue:
            jours_retard = (
                emprunt.date_retour_reelle - emprunt.date_retour_prevue
            ).days
            emprunt.penalite = jours_retard * 0.50  # 0.50€ par jour

        emprunt.save(update_fields=["statut", "date_retour_reelle", "penalite"])
        disponible = (
            exemplaire.etat not in ("perdu", "détérioré")
            and not Emprunt.objects.filter(
                exemplaire=exemplaire, statut__in=STATUTS_EMPRUNT_OCCUPANT
            ).exists()
            and exemplaires_empruntables(exemplaire.livre) > 0
        )
        return Response(
            {
                "detail": "Livre rendu.",
                "id": emprunt.id,
                "penalite": float(emprunt.penalite),
                "exemplaire_disponible": disponible,
            }
        )

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def renouveler(self, request, pk=None):
        """Renouvelle un emprunt."""
        emprunt = self.get_object()
        if emprunt.statut not in STATUTS_EMPRUNT_ACTIF:
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
        qs = self.get_queryset().filter(
            statut__in=STATUTS_EMPRUNT_ACTIF, date_retour_prevue__lt=today
        )
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
        _local_user(self.request)
        qs = Reservation.objects.filter(
            utilisateur__etablissement_id=self.request.tenant.pk
        ).select_related("livre", "utilisateur")
        user = self.request.user
        # Un utilisateur ne voit que ses propres réservations (sauf bibliothécaire)
        if not (
            user.is_staff or request_has_business_access(
                self.request, "bibliotheque.change_livre", ("bibliothecaire", "responsable_bibliotheque")
            )
        ):
            qs = qs.filter(utilisateur=user)
        return qs

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        if set(request.data) != {"livre"}:
            raise ValidationError("Seul le titre peut être fourni.")
        serializer = ReservationClaimSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return _reclamer(serializer.validated_data["livre"], request)

    def update(self, request, *args, **kwargs):
        raise MethodNotAllowed(request.method, detail="Utiliser les actions annuler et recuperer.")

    def destroy(self, request, *args, **kwargs):
        raise MethodNotAllowed(request.method, detail="Une réservation ne peut être supprimée.")

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def annuler(self, request, pk=None):
        """Annule une réservation."""
        _local_user(request)
        livre_id = get_object_or_404(
            self.get_queryset().values_list("livre_id", flat=True), pk=pk
        )
        Livre.objects.select_for_update().get(pk=livre_id)
        reservation = self.get_object()
        if reservation.statut not in STATUTS_RESERVATION_ACTIVE:
            return Response(
                {"error": "Cette réservation ne peut pas être annulée."}, status=400
            )
        reservation.statut = "annulee"
        reservation.save(update_fields=["statut"])
        return Response({"detail": "Réservation annulée.", "id": reservation.id})

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def recuperer(self, request, pk=None):
        """Remet un exemplaire libre au premier demandeur, en enregistrant son emprunt."""
        _bibliothecaire(request)
        livre_id = get_object_or_404(
            self.get_queryset().values_list("livre_id", flat=True), pk=pk
        )
        Livre.objects.select_for_update().get(pk=livre_id)
        reservation = self.get_object()
        if reservation.statut not in STATUTS_RESERVATION_ACTIVE:
            raise ValidationError({"reservation": "Réservation déjà clôturée."})
        premiere = Reservation.objects.filter(
            livre_id=livre_id, statut__in=STATUTS_RESERVATION_ACTIVE
        ).order_by("date_reservation", "pk").first()
        if premiere.pk != reservation.pk:
            raise ValidationError({"reservation": "Une réservation antérieure est prioritaire."})
        if set(request.data) != {"exemplaire"}:
            raise ValidationError("Seul l'exemplaire à remettre peut être fourni.")
        remise = ReservationRemiseSerializer(data=request.data)
        remise.is_valid(raise_exception=True)
        item = Exemplaire.objects.select_for_update().get(pk=remise.validated_data["exemplaire"].pk)
        if item.livre_id != livre_id or item.etat in ("perdu", "détérioré"):
            raise ValidationError({"exemplaire": "Exemplaire indisponible pour ce titre."})
        if Emprunt.objects.filter(exemplaire=item, statut__in=STATUTS_EMPRUNT_OCCUPANT).exists():
            raise ValidationError({"exemplaire": "Exemplaire déjà emprunté."})
        if reservation.utilisateur.etablissement_id != request.tenant.pk:
            raise ValidationError({"utilisateur": "Compte hors établissement."})
        aujourd_hui = timezone.now().date()
        emprunt = Emprunt.objects.create(
            exemplaire=item, emprunteur=reservation.utilisateur,
            date_emprunt=aujourd_hui, date_retour_prevue=aujourd_hui + timedelta(days=21),
        )
        reservation.statut = "recuperee"
        reservation.save(update_fields=["statut"])
        return Response({"detail": "Réservation remise.", "id": reservation.pk, "emprunt": emprunt.pk})
