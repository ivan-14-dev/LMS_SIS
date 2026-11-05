"""Serializers for notes (SIS Supérieur)."""

from rest_framework import serializers

from sis_common.academic_configuration import validate_rule_criteria
from sis_common.authorization import user_has_any_role
from sis_common.grade_entry import GradeUpdateSerializerMixin, validate_assessment_scale
from sis_common.learning_offerings import ModelValidationSerializerMixin
from sis_common.serializers import TenantBoundSerializerMixin
from sis_common.submission_windows import get_submission_window_alert, get_submission_window_status

from .models import Evaluation, MoyenneECUE, MoyenneUE, Note, RegleValidation


class EvaluationListSerializer(serializers.ModelSerializer):
    """Serializer léger pour les listes d'évaluations."""

    ecue_nom = serializers.CharField(source="ecue.nom", read_only=True)
    ecue_code = serializers.CharField(source="ecue.code", read_only=True)
    modalite_display = serializers.CharField(source="get_modalite_display", read_only=True)
    enseignant_nom = serializers.CharField(source="enseignant.get_full_name", read_only=True)
    soumission_statut = serializers.SerializerMethodField()
    soumission_alerte = serializers.SerializerMethodField()

    class Meta:
        model = Evaluation
        fields = [
            "id",
            "offre_configuration",
            "titre",
            "type",
            "modalite",
            "modalite_display",
            "ecue",
            "ecue_nom",
            "ecue_code",
            "date",
            "heure_debut",
            "duree_minutes",
            "debut_soumission",
            "fin_soumission",
            "bareme",
            "coefficient",
            "ponderation",
            "enseignant_nom",
            "anonyme",
            "soumission_statut",
            "soumission_alerte",
        ]

    def get_soumission_statut(self, obj):
        return get_submission_window_status(obj)

    def get_soumission_alerte(self, obj):
        request = self.context.get("request")
        configuration = getattr(getattr(request, "tenant", None), "configuration_academique", {})
        return get_submission_window_alert(obj, configuration, "evaluation")


class EvaluationDetailSerializer(
    ModelValidationSerializerMixin, TenantBoundSerializerMixin, serializers.ModelSerializer
):
    """Serializer complet pour le détail d'une évaluation."""

    ecue_nom = serializers.CharField(source="ecue.nom", read_only=True)
    modalite_display = serializers.CharField(source="get_modalite_display", read_only=True)
    enseignant_nom = serializers.CharField(source="enseignant.get_full_name", read_only=True)
    semestre_libelle = serializers.CharField(source="semestre", read_only=True)
    nb_notes = serializers.SerializerMethodField()
    soumission_statut = serializers.SerializerMethodField()
    soumission_alerte = serializers.SerializerMethodField()

    class Meta:
        model = Evaluation
        fields = [
            "id",
            "offre_configuration",
            "titre",
            "type",
            "description",
            "ecue",
            "ecue_nom",
            "semestre",
            "semestre_libelle",
            "date",
            "heure_debut",
            "duree_minutes",
            "debut_soumission",
            "fin_soumission",
            "bareme",
            "coefficient",
            "ponderation",
            "modalite",
            "modalite_display",
            "enseignant",
            "enseignant_nom",
            "anonyme",
            "nb_notes",
            "soumission_statut",
            "soumission_alerte",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_nb_notes(self, obj):
        return obj.notes.exclude(valeur__isnull=True, resultat={}).count()

    def get_soumission_statut(self, obj):
        return get_submission_window_status(obj)

    def get_soumission_alerte(self, obj):
        request = self.context.get("request")
        configuration = getattr(getattr(request, "tenant", None), "configuration_academique", {})
        return get_submission_window_alert(obj, configuration, "evaluation")

    def validate(self, attrs):
        attrs = super().validate(attrs)
        validate_assessment_scale(attrs, self.instance)
        ecue = attrs.get("ecue", getattr(self.instance, "ecue", None))
        semestre = attrs.get("semestre", getattr(self.instance, "semestre", None))
        enseignant = attrs.get("enseignant", getattr(self.instance, "enseignant", None))
        request = self.context.get("request")
        tenant = getattr(request, "tenant", None)
        if tenant and semestre and semestre.annee_universitaire.universite_id != tenant.pk:
            raise serializers.ValidationError({"semestre": "Ce semestre appartient à un autre établissement."})
        if tenant and ecue and ecue.ue.maquette.annee_universitaire.universite_id != tenant.pk:
            raise serializers.ValidationError({"ecue": "Cet ECUE appartient à un autre établissement."})
        user = getattr(request, "user", None)
        if user and not user.is_superuser and user_has_any_role(user, ("enseignant", "chercheur")):
            if enseignant and enseignant.pk != user.pk:
                raise serializers.ValidationError(
                    {"enseignant": "Vous ne pouvez créer une évaluation pour un autre enseignant."}
                )
        debut_soumission = attrs.get("debut_soumission", getattr(self.instance, "debut_soumission", None))
        fin_soumission = attrs.get("fin_soumission", getattr(self.instance, "fin_soumission", None))
        if debut_soumission and fin_soumission and fin_soumission < debut_soumission:
            raise serializers.ValidationError(
                {"fin_soumission": "La fin de soumission doit être postérieure au début."}
            )
        return attrs


class NoteSerializer(ModelValidationSerializerMixin, GradeUpdateSerializerMixin, serializers.ModelSerializer):
    """Serializer pour les notes."""

    etudiant_matricule = serializers.CharField(source="etudiant.matricule", read_only=True)
    etudiant_nom = serializers.CharField(source="etudiant.user.get_full_name", read_only=True)
    statut_display = serializers.CharField(source="get_statut_display", read_only=True)
    evaluation_titre = serializers.CharField(source="evaluation.titre", read_only=True)
    bareme = serializers.DecimalField(source="evaluation.bareme", max_digits=5, decimal_places=2, read_only=True)

    class Meta:
        model = Note
        fields = [
            "id",
            "evaluation",
            "evaluation_titre",
            "etudiant",
            "etudiant_matricule",
            "etudiant_nom",
            "valeur",
            "bareme",
            "resultat",
            "resultat_offre",
            "numero_anonyme",
            "appreciation",
            "statut",
            "statut_display",
            "date_saisie",
            "saisi_par",
            "modifie_le",
        ]
        read_only_fields = ["id", "date_saisie"]


class NoteSaisieSerializer(serializers.Serializer):
    """Serializer pour la saisie en masse de notes."""

    etudiant_id = serializers.IntegerField()
    valeur = serializers.DecimalField(max_digits=5, decimal_places=2, allow_null=True)
    resultat = serializers.JSONField(required=False, default=dict)
    statut = serializers.ChoiceField(choices=Note.STATUT_CHOICES, default="presente")
    appreciation = serializers.CharField(required=False, allow_blank=True)


class MoyenneECUESerializer(serializers.ModelSerializer):
    """Serializer pour les moyennes ECUE."""

    etudiant_matricule = serializers.CharField(source="etudiant.matricule", read_only=True)
    etudiant_nom = serializers.CharField(source="etudiant.user.get_full_name", read_only=True)
    ecue_nom = serializers.CharField(source="ecue.nom", read_only=True)
    ecue_code = serializers.CharField(source="ecue.code", read_only=True)

    class Meta:
        model = MoyenneECUE
        fields = [
            "id",
            "etudiant",
            "etudiant_matricule",
            "etudiant_nom",
            "ecue",
            "ecue_nom",
            "ecue_code",
            "semestre",
            "moyenne",
            "valide",
            "date_calcul",
        ]
        read_only_fields = ["id", "date_calcul"]


class MoyenneUESerializer(serializers.ModelSerializer):
    """Serializer pour les moyennes UE."""

    etudiant_matricule = serializers.CharField(source="etudiant.matricule", read_only=True)
    etudiant_nom = serializers.CharField(source="etudiant.user.get_full_name", read_only=True)
    ue_nom = serializers.CharField(source="ue.nom", read_only=True)
    ue_code = serializers.CharField(source="ue.code", read_only=True)

    class Meta:
        model = MoyenneUE
        fields = [
            "id",
            "etudiant",
            "etudiant_matricule",
            "etudiant_nom",
            "ue",
            "ue_nom",
            "ue_code",
            "semestre",
            "moyenne",
            "credits_obtenus",
            "capitalisee",
            "date_calcul",
        ]
        read_only_fields = ["id", "date_calcul"]


class RegleValidationSerializer(serializers.ModelSerializer):
    class Meta:
        model = RegleValidation
        fields = "__all__"

    def validate_criteres(self, value):
        validate_rule_criteria(value)
        return value

    def validate(self, attrs):
        semestre = attrs.get("semestre", getattr(self.instance, "semestre", None))
        annee = attrs.get(
            "annee_universitaire",
            getattr(self.instance, "annee_universitaire", None),
        )
        if semestre and semestre.annee_universitaire_id != annee.id:
            raise serializers.ValidationError({"semestre": "Le semestre doit appartenir à l'année de la règle."})
        return attrs
