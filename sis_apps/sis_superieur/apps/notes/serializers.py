"""Serializers for notes (SIS Supérieur)."""

from rest_framework import serializers
from sis_common.academic_configuration import validate_rule_criteria

from .models import Evaluation, MoyenneECUE, MoyenneUE, Note, RegleValidation


class EvaluationListSerializer(serializers.ModelSerializer):
    """Serializer léger pour les listes d'évaluations."""

    ecue_nom = serializers.CharField(source="ecue.nom", read_only=True)
    ecue_code = serializers.CharField(source="ecue.code", read_only=True)
    modalite_display = serializers.CharField(source="get_modalite_display", read_only=True)
    enseignant_nom = serializers.CharField(source="enseignant.get_full_name", read_only=True)

    class Meta:
        model = Evaluation
        fields = [
            "id",
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
            "bareme",
            "coefficient",
            "ponderation",
            "enseignant_nom",
        ]


class EvaluationDetailSerializer(serializers.ModelSerializer):
    """Serializer complet pour le détail d'une évaluation."""

    ecue_nom = serializers.CharField(source="ecue.nom", read_only=True)
    modalite_display = serializers.CharField(source="get_modalite_display", read_only=True)
    enseignant_nom = serializers.CharField(source="enseignant.get_full_name", read_only=True)
    semestre_libelle = serializers.CharField(source="semestre.libelle", read_only=True)
    nb_notes = serializers.SerializerMethodField()

    class Meta:
        model = Evaluation
        fields = [
            "id",
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
            "bareme",
            "coefficient",
            "ponderation",
            "modalite",
            "modalite_display",
            "enseignant",
            "enseignant_nom",
            "anonyme",
            "nb_notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_nb_notes(self, obj):
        return obj.notes.exclude(valeur__isnull=True).count()


class NoteSerializer(serializers.ModelSerializer):
    """Serializer pour les notes."""

    etudiant_matricule = serializers.CharField(source="etudiant.matricule", read_only=True)
    etudiant_nom = serializers.CharField(source="etudiant.user.get_full_name", read_only=True)
    statut_display = serializers.CharField(source="get_statut_display", read_only=True)
    evaluation_titre = serializers.CharField(source="evaluation.titre", read_only=True)

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
