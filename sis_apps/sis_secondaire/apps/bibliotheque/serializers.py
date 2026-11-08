"""Serializers for bibliotheque (SIS Secondaire)."""

from rest_framework import serializers

from sis_common.authorization import is_current_tenant_user
from sis_common.digital_library import DigitalLibrarySerializerMixin, LibraryFileField
from sis_common.exam_files import validate_exam_copy

from .models import Emprunt, Exemplaire, Livre, Reservation


def reservation_prioritaire(livre, request):
    premiere = (
        livre.reservations.filter(statut__in=("en_attente", "disponible")).order_by("date_reservation", "pk").first()
    )
    return premiere is None or bool(
        request is not None and is_current_tenant_user(request) and premiere.utilisateur_id == request.user.pk
    )


class LivreListSerializer(DigitalLibrarySerializerMixin, serializers.ModelSerializer):
    """Serializer léger pour les listes de livres."""

    nb_exemplaires = serializers.SerializerMethodField()
    disponibles = serializers.SerializerMethodField()
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
            "annee",
            "categorie",
            "cote",
            "nb_exemplaires",
            "disponibles",
            "ressource_numerique",
            "peut_consulter_ressource",
            "licence_active",
            "licence_reference",
            "licence_expire_le",
        ]

    def get_nb_exemplaires(self, obj):
        return obj.exemplaires.exclude(etat="perdu").count()

    def get_disponibles(self, obj):
        if not reservation_prioritaire(obj, self.context.get("request")):
            return 0
        return (
            obj.exemplaires.filter(etat__in=("neuf", "bon", "use"))
            .exclude(emprunts__statut__in=("en_cours", "en_retard", "perdu"))
            .count()
        )


class LivreDetailSerializer(DigitalLibrarySerializerMixin, serializers.ModelSerializer):
    """Serializer complet pour un livre."""

    exemplaires = serializers.SerializerMethodField()
    peut_consulter_ressource = serializers.SerializerMethodField()
    ressource_numerique = LibraryFileField(required=False, allow_null=True, validators=[validate_exam_copy])

    class Meta:
        model = Livre
        fields = [
            "id",
            "isbn",
            "titre",
            "auteurs",
            "editeur",
            "annee",
            "categorie",
            "mots_cles",
            "resume",
            "image_couverture",
            "cote",
            "nombre_exemplaires",
            "exemplaires",
            "ressource_numerique",
            "peut_consulter_ressource",
            "licence_active",
            "licence_reference",
            "licence_expire_le",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_exemplaires(self, obj):
        return ExemplaireSerializer(obj.exemplaires.all(), many=True, context=self.context).data


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
            "disponible",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_disponible(self, obj):
        return (
            obj.etat in ("neuf", "bon", "use")
            and not obj.emprunts.filter(statut__in=("en_cours", "en_retard", "perdu")).exists()
            and reservation_prioritaire(obj.livre, self.context.get("request"))
        )


class EmpruntSerializer(serializers.ModelSerializer):
    """Serializer pour les emprunts."""

    exemplaire_code = serializers.CharField(
        source="exemplaire.code_barre", read_only=True
    )
    livre_titre = serializers.CharField(source="exemplaire.livre.titre", read_only=True)
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
            "exemplaire_code",
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

    def validate_emprunteur(self, value):
        tenant = getattr(self.context.get("request"), "tenant", None)
        if tenant is None or value.etablissement_id != tenant.pk:
            raise serializers.ValidationError("L'emprunteur doit appartenir à l'établissement.")
        return value

    def get_jours_retard(self, obj):
        if obj.statut != "en_cours":
            return 0
        from django.utils import timezone

        today = timezone.now().date()
        if today > obj.date_retour_prevue:
            return (today - obj.date_retour_prevue).days
        return 0


class ReservationSerializer(serializers.ModelSerializer):
    livre_titre = serializers.CharField(source="livre.titre", read_only=True)

    class Meta:
        model = Reservation
        fields = [
            "id", "livre", "livre_titre", "utilisateur", "date_reservation",
            "statut", "emprunt",
        ]
        read_only_fields = ["id", "utilisateur", "date_reservation", "statut", "emprunt"]


class ReservationFulfilSerializer(serializers.Serializer):
    exemplaire = serializers.PrimaryKeyRelatedField(queryset=Exemplaire.objects.all())
    date_retour_prevue = serializers.DateField()

    def validate_date_retour_prevue(self, value):
        from django.utils import timezone

        if value <= timezone.localdate():
            raise serializers.ValidationError("La date de retour doit être future.")
        return value
