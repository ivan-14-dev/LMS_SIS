"""Serializers for bibliotheque (SIS Supérieur)."""

from rest_framework import serializers

from sis_common.authorization import is_current_tenant_user
from sis_common.digital_library import DigitalLibrarySerializerMixin, LibraryFileField
from sis_common.exam_files import validate_exam_copy

from .models import Emprunt, Exemplaire, Livre, Reservation

STATUTS_EMPRUNT_ACTIF = ("en_cours", "renouvele")
STATUTS_EMPRUNT_OCCUPANT = (*STATUTS_EMPRUNT_ACTIF, "en_retard", "perdu")


def exemplaires_disponibles(livre):
    return (
        Exemplaire.objects.filter(livre=livre)
        .exclude(etat__in=("perdu", "détérioré"))
        .exclude(emprunts__statut__in=STATUTS_EMPRUNT_OCCUPANT)
        .count()
    )


def exemplaires_empruntables(livre, request=None):
    reservations = livre.reservations.filter(statut__in=("en_attente", "disponible"))
    disponibles = exemplaires_disponibles(livre)
    accessibles = max(0, disponibles - reservations.count())
    if disponibles and request is not None and is_current_tenant_user(request):
        premiere = reservations.order_by("date_reservation", "pk").first()
        if premiere and premiere.utilisateur_id == request.user.pk:
            accessibles += 1
        elif reservations.filter(utilisateur=request.user).exists():
            return 0
    return accessibles


class ReservationClaimSerializer(serializers.Serializer):
    livre = serializers.PrimaryKeyRelatedField(queryset=Livre.objects.all())


class ReservationRemiseSerializer(serializers.Serializer):
    exemplaire = serializers.PrimaryKeyRelatedField(queryset=Exemplaire.objects.all())


class LivreListSerializer(DigitalLibrarySerializerMixin, serializers.ModelSerializer):
    """Serializer léger pour les listes de livres."""

    nb_exemplaires_disponibles = serializers.SerializerMethodField()
    peut_consulter_ressource = serializers.SerializerMethodField()
    ressource_numerique = LibraryFileField(read_only=True)

    class Meta:
        model = Livre
        fields = [
            "id",
            "isbn",
            "titre",
            "auteurs",
            "editeur",
            "annee_publication",
            "categorie",
            "cote",
            "nombre_exemplaires",
            "nb_exemplaires_disponibles",
            "image_couverture",
            "ressource_numerique",
            "peut_consulter_ressource",
            "licence_active",
            "licence_reference",
            "licence_expire_le",
        ]

    def get_nb_exemplaires_disponibles(self, obj):
        return exemplaires_empruntables(obj, self.context.get("request"))


class LivreDetailSerializer(DigitalLibrarySerializerMixin, serializers.ModelSerializer):
    """Serializer complet pour un livre."""

    nb_exemplaires_disponibles = serializers.SerializerMethodField()
    nb_reservations = serializers.SerializerMethodField()
    peut_consulter_ressource = serializers.SerializerMethodField()
    ressource_numerique = LibraryFileField(required=False, allow_null=True, validators=[validate_exam_copy])

    class Meta:
        model = Livre
        fields = [
            "id",
            "isbn",
            "titre",
            "sous_titre",
            "auteurs",
            "editeur",
            "annee_publication",
            "langue",
            "categorie",
            "mots_cles",
            "resume",
            "image_couverture",
            "cote",
            "nombre_exemplaires",
            "nb_exemplaires_disponibles",
            "ressource_numerique",
            "peut_consulter_ressource",
            "licence_active",
            "licence_reference",
            "licence_expire_le",
            "url_externe",
            "base_donnees",
            "nb_reservations",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_nb_exemplaires_disponibles(self, obj):
        return exemplaires_empruntables(obj, self.context.get("request"))

    def get_nb_reservations(self, obj):
        return obj.reservations.filter(statut="en_attente").count()


class ExemplaireSerializer(serializers.ModelSerializer):
    """Serializer pour les exemplaires."""

    livre_titre = serializers.CharField(source="livre.titre", read_only=True)
    etat_display = serializers.CharField(source="get_etat_display", read_only=True)
    disponible = serializers.SerializerMethodField()

    class Meta:
        model = Exemplaire
        fields = [
            "id",
            "livre",
            "livre_titre",
            "code_barre",
            "etat",
            "etat_display",
            "localisation",
            "date_acquisition",
            "prix_acquisition",
            "disponible",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_disponible(self, obj):
        return (
            obj.etat not in ("perdu", "détérioré")
            and not obj.emprunts.filter(statut__in=STATUTS_EMPRUNT_OCCUPANT).exists()
            and exemplaires_empruntables(obj.livre, self.context.get("request")) > 0
        )


class EmpruntSerializer(serializers.ModelSerializer):
    """Serializer pour les emprunts."""

    livre_titre = serializers.CharField(source="exemplaire.livre.titre", read_only=True)
    code_barre = serializers.CharField(source="exemplaire.code_barre", read_only=True)
    emprunteur_nom = serializers.CharField(
        source="emprunteur.get_full_name", read_only=True
    )
    statut_display = serializers.CharField(source="get_statut_display", read_only=True)
    jours_retard = serializers.SerializerMethodField()

    class Meta:
        model = Emprunt
        fields = [
            "id",
            "exemplaire",
            "code_barre",
            "livre_titre",
            "emprunteur",
            "emprunteur_nom",
            "date_emprunt",
            "date_retour_prevue",
            "date_retour_reelle",
            "statut",
            "statut_display",
            "nb_renouvellements",
            "penalite",
            "jours_retard",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]
        extra_kwargs = {
            "emprunteur": {"required": False},
            "date_emprunt": {"required": False},
            "date_retour_prevue": {"required": False},
        }

    def get_jours_retard(self, obj):
        if obj.statut in STATUTS_EMPRUNT_ACTIF and obj.date_retour_prevue:
            from django.utils import timezone

            today = timezone.now().date()
            if today > obj.date_retour_prevue:
                return (today - obj.date_retour_prevue).days
        return 0


class ReservationSerializer(serializers.ModelSerializer):
    """Serializer pour les réservations."""

    livre_titre = serializers.CharField(source="livre.titre", read_only=True)
    utilisateur_nom = serializers.CharField(
        source="utilisateur.get_full_name", read_only=True
    )
    statut_display = serializers.CharField(source="get_statut_display", read_only=True)
    position_file = serializers.SerializerMethodField()

    class Meta:
        model = Reservation
        fields = [
            "id",
            "livre",
            "livre_titre",
            "utilisateur",
            "utilisateur_nom",
            "date_reservation",
            "statut",
            "statut_display",
            "date_notification",
            "position_file",
        ]
        read_only_fields = ["id", "date_reservation"]

    def get_position_file(self, obj):
        if obj.statut == "en_attente":
            return (
                Reservation.objects.filter(
                    livre=obj.livre,
                    statut="en_attente",
                    date_reservation__lt=obj.date_reservation,
                ).count()
                + 1
            )
        return None
