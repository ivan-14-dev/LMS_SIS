"""Serializers for presences (SIS Secondaire)."""

from rest_framework import serializers

from sis_common.authorization import user_has_any_role
from sis_common.serializers import TenantBoundSerializerMixin

from .models import Appel, Justificatif, Presence


def validate_attendance(request, appel, eleve=None):
    if appel.statut != "ouvert" or appel.creneau.classe.annee_scolaire.cloturee:
        raise serializers.ValidationError({"appel": "L'appel ou son année scolaire est fermé."})
    if request:
        if appel.creneau.classe.etablissement_id != request.tenant.pk:
            raise serializers.ValidationError({"appel": "Cet appel appartient à un autre établissement."})
        user = request.user
        if not user.is_staff and user_has_any_role(user, ("enseignant",)) and appel.enseignant.user_id != user.pk:
            raise serializers.ValidationError({"appel": "Vous ne pouvez saisir que vos propres appels."})
    if eleve and eleve.classe_actuelle_id != appel.creneau.classe_id:
        raise serializers.ValidationError({"eleve": "Cet élève n'appartient pas à la classe de l'appel."})


class AppelListSerializer(serializers.ModelSerializer):
    """Serializer léger pour les listes d'appels."""

    creneau_libelle = serializers.SerializerMethodField()
    enseignant_nom = serializers.CharField(source="enseignant.user.get_full_name", read_only=True)
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


class AppelDetailSerializer(TenantBoundSerializerMixin, serializers.ModelSerializer):
    """Serializer complet pour un appel."""

    creneau_libelle = serializers.SerializerMethodField()
    enseignant_nom = serializers.CharField(source="enseignant.user.get_full_name", read_only=True)

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
        read_only_fields = [
            "id",
            "statut",
            "date_validation",
            "date_saisie",
            "created_at",
            "updated_at",
        ]

    def get_creneau_libelle(self, obj):
        return str(obj.creneau)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        creneau = attrs.get("creneau", getattr(self.instance, "creneau", None))
        enseignant = attrs.get("enseignant", getattr(self.instance, "enseignant", None))
        if creneau and enseignant and creneau.enseignant_id != enseignant.pk:
            raise serializers.ValidationError({"enseignant": "L'enseignant doit correspondre au créneau."})
        if creneau and enseignant:
            candidate = Appel(creneau=creneau, enseignant=enseignant)
            if self.instance:
                validate_attendance(self.context.get("request"), self.instance)
                if creneau.pk != self.instance.creneau_id and self.instance.presences.exists():
                    raise serializers.ValidationError(
                        {"creneau": "Un appel déjà renseigné ne peut changer de créneau."}
                    )
            validate_attendance(self.context.get("request"), candidate)
        return attrs


class PresenceSerializer(TenantBoundSerializerMixin, serializers.ModelSerializer):
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
        read_only_fields = ["id", "notifie_parent", "date_notification"]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        appel = attrs.get("appel", getattr(self.instance, "appel", None))
        eleve = attrs.get("eleve", getattr(self.instance, "eleve", None))
        if self.instance and (appel.pk != self.instance.appel_id or eleve.pk != self.instance.eleve_id):
            raise serializers.ValidationError("L'appel et l'élève d'une présence existante ne peuvent être changés.")
        if appel:
            validate_attendance(self.context.get("request"), appel, eleve)
        return attrs

    def get_a_justificatif(self, obj):
        return hasattr(obj, "justificatif")


class PresenceSaisieSerializer(serializers.Serializer):
    """Serializer pour la saisie en masse de présences."""

    eleve_id = serializers.IntegerField()
    statut = serializers.ChoiceField(choices=Presence.STATUT_CHOICES, default="present")
    retard_minutes = serializers.IntegerField(required=False, allow_null=True, min_value=0, max_value=32767)
    commentaire = serializers.CharField(required=False, allow_blank=True)


class JustificatifSerializer(serializers.ModelSerializer):
    """Les décisions de validation passent par les actions accepter/refuser."""

    eleve_nom = serializers.CharField(source="presence.eleve.user.get_full_name", read_only=True)
    date_absence = serializers.DateField(source="presence.appel.date", read_only=True)
    statut_display = serializers.CharField(source="get_statut_display", read_only=True)
    valide_par_nom = serializers.CharField(source="valide_par.user.get_full_name", read_only=True)

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
        read_only_fields = [
            "id",
            "date_depot",
            "statut",
            "valide_par",
            "date_validation",
            "commentaire_validation",
        ]
