"""Serializers for presences (SIS Secondaire)."""

from rest_framework import serializers

from .models import Appel, Justificatif, Presence


class AppelListSerializer(serializers.ModelSerializer):
    """Serializer léger pour les listes d'appels."""

    creneau_libelle = serializers.SerializerMethodField()
    enseignant_nom = serializers.CharField(
        source="enseignant.user.get_full_name", read_only=True
    )
    statut_display = serializers.SerializerMethodField()
    nb_presents = serializers.SerializerMethodField()
    nb_absents = serializers.SerializerMethodField()

    class Meta:
        model = Appel
        fields = [
            "id",
            "creneau",
            "creneau_libelle",
            "date",
            "enseignant",
            "enseignant_nom",
            "statut",
            "statut_display",
            "nb_presents",
            "nb_absents",
            "date_saisie",
        ]

    def get_creneau_libelle(self, obj):
        return str(obj.creneau)

    def get_statut_display(self, obj):
        return dict(obj._meta.get_field("statut").choices).get(obj.statut, "")

    def get_nb_presents(self, obj):
        return obj.presences.filter(statut="present").count()

    def get_nb_absents(self, obj):
        return obj.presences.filter(statut__in=["absent", "absent_justifie"]).count()


class AppelDetailSerializer(serializers.ModelSerializer):
    """Serializer complet pour un appel."""

    creneau_libelle = serializers.SerializerMethodField()
    enseignant_nom = serializers.CharField(
        source="enseignant.user.get_full_name", read_only=True
    )

    class Meta:
        model = Appel
        fields = [
            "id",
            "creneau",
            "creneau_libelle",
            "date",
            "enseignant",
            "enseignant_nom",
            "statut",
            "commentaire_global",
            "date_saisie",
            "date_validation",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "date_saisie", "created_at", "updated_at"]

    def get_creneau_libelle(self, obj):
        return str(obj.creneau)


class PresenceSerializer(serializers.ModelSerializer):
    """Serializer pour les présences."""

    eleve_matricule = serializers.CharField(source="eleve.matricule", read_only=True)
    eleve_nom = serializers.CharField(source="eleve.user.get_full_name", read_only=True)
    statut_display = serializers.CharField(source="get_statut_display", read_only=True)
    a_justificatif = serializers.SerializerMethodField()

    class Meta:
        model = Presence
        fields = [
            "id",
            "appel",
            "eleve",
            "eleve_matricule",
            "eleve_nom",
            "statut",
            "statut_display",
            "retard_minutes",
            "sortie_heure",
            "commentaire",
            "notifie_parent",
            "date_notification",
            "a_justificatif",
        ]
        read_only_fields = ["id"]

    def get_a_justificatif(self, obj):
        return hasattr(obj, "justificatif")


class PresenceSaisieSerializer(serializers.Serializer):
    """Serializer pour la saisie en masse de présences."""

    eleve_id = serializers.IntegerField()
    statut = serializers.ChoiceField(choices=Presence.STATUT_CHOICES, default="present")
    retard_minutes = serializers.IntegerField(required=False, allow_null=True)
    commentaire = serializers.CharField(required=False, allow_blank=True)


class JustificatifSerializer(serializers.ModelSerializer):
    """Serializer pour les justificatifs."""

    eleve_nom = serializers.CharField(
        source="presence.eleve.user.get_full_name", read_only=True
    )
    date_absence = serializers.DateField(source="presence.appel.date", read_only=True)
    statut_display = serializers.CharField(source="get_statut_display", read_only=True)
    valide_par_nom = serializers.CharField(
        source="valide_par.user.get_full_name", read_only=True
    )

    class Meta:
        model = Justificatif
        fields = [
            "id",
            "presence",
            "eleve_nom",
            "date_absence",
            "motif",
            "document",
            "date_depot",
            "statut",
            "statut_display",
            "valide_par",
            "valide_par_nom",
            "date_validation",
            "commentaire_validation",
        ]
        read_only_fields = ["id", "date_depot"]
