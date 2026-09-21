"""Serializers for notes (SIS Secondaire)."""

from apps.classes.models import ProgrammeMatiere
from apps.eleves.models import AffectationMatiereIndividuelle
from rest_framework import serializers
from sis_common.academic_configuration import validate_rule_criteria

from .models import Bulletin, Evaluation, Note, RegleValidation


class EvaluationListSerializer(serializers.ModelSerializer):
    """Serializer léger pour les listes d'évaluations."""

    matiere_nom = serializers.CharField(source="matiere.nom", read_only=True)
    classe_nom = serializers.CharField(source="classe.nom", read_only=True)
    type_display = serializers.CharField(source="get_type_display", read_only=True)
    enseignant_nom = serializers.CharField(source="enseignant.user.get_full_name", read_only=True)
    eleve_cible_matricule = serializers.CharField(source="eleve_cible.matricule", read_only=True)
    eleve_cible_nom = serializers.CharField(source="eleve_cible.user.get_full_name", read_only=True)
    individualisee = serializers.SerializerMethodField()
    nb_notes = serializers.SerializerMethodField()
    notes_saisies = serializers.SerializerMethodField()

    class Meta:
        model = Evaluation
        fields = [
            "id",
            "titre",
            "type",
            "type_display",
            "matiere",
            "matiere_nom",
            "classe",
            "classe_nom",
            "date",
            "heure_debut",
            "duree_minutes",
            "bareme",
            "coefficient",
            "ponderation",
            "eleve_cible",
            "eleve_cible_matricule",
            "eleve_cible_nom",
            "individualisee",
            "nb_notes",
            "notes_saisies",
            "enseignant_nom",
        ]

    def get_individualisee(self, obj):
        return bool(obj.eleve_cible_id)

    def get_nb_notes(self, obj):
        return obj.notes.exclude(valeur__isnull=True).count()

    def get_notes_saisies(self, obj):
        return self.get_nb_notes(obj) > 0


class EvaluationDetailSerializer(serializers.ModelSerializer):
    """Serializer complet pour une évaluation."""

    matiere_nom = serializers.CharField(source="matiere.nom", read_only=True)
    classe_nom = serializers.CharField(source="classe.nom", read_only=True)
    type_display = serializers.CharField(source="get_type_display", read_only=True)
    enseignant_nom = serializers.CharField(source="enseignant.user.get_full_name", read_only=True)
    periode_libelle = serializers.CharField(source="periode.libelle", read_only=True)
    nb_notes = serializers.SerializerMethodField()
    eleve_cible_matricule = serializers.CharField(source="eleve_cible.matricule", read_only=True)
    eleve_cible_nom = serializers.CharField(source="eleve_cible.user.get_full_name", read_only=True)
    individualisee = serializers.SerializerMethodField()

    class Meta:
        model = Evaluation
        fields = [
            "id",
            "titre",
            "type",
            "type_display",
            "description",
            "matiere",
            "matiere_nom",
            "classe",
            "classe_nom",
            "periode",
            "periode_libelle",
            "date",
            "heure_debut",
            "duree_minutes",
            "bareme",
            "coefficient",
            "ponderation",
            "enseignant",
            "enseignant_nom",
            "eleve_cible",
            "eleve_cible_matricule",
            "eleve_cible_nom",
            "individualisee",
            "nb_notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_nb_notes(self, obj):
        return obj.notes.exclude(valeur__isnull=True).count()

    def get_individualisee(self, obj):
        return bool(obj.eleve_cible_id)

    def validate(self, attrs):
        classe = attrs.get("classe", getattr(self.instance, "classe", None))
        matiere = attrs.get("matiere", getattr(self.instance, "matiere", None))
        eleve_cible = attrs.get("eleve_cible", getattr(self.instance, "eleve_cible", None))
        if not eleve_cible:
            return attrs
        class_member = eleve_cible.classe_actuelle_id == getattr(classe, "id", None) or classe.inscriptions.filter(
            eleve=eleve_cible,
            statut__in=("en_cours", "validee"),
        ).exists()
        if not class_member:
            raise serializers.ValidationError(
                {"eleve_cible": "L'élève ciblé doit appartenir à la classe de l'évaluation."}
            )
        subject_in_program = ProgrammeMatiere.objects.filter(classe=classe, matiere=matiere).exists()
        if not subject_in_program and not AffectationMatiereIndividuelle.objects.filter(
            eleve=eleve_cible,
            annee_scolaire=classe.annee_scolaire,
            matiere=matiere,
        ).exists():
            raise serializers.ValidationError(
                {
                    "eleve_cible": (
                        "L'élève ciblé doit avoir cette matière dans son programme de classe ou via une affectation individuelle."
                    )
                }
            )
        return attrs


class NoteSerializer(serializers.ModelSerializer):
    """Serializer pour les notes."""

    eleve_matricule = serializers.CharField(source="eleve.matricule", read_only=True)
    eleve_nom = serializers.CharField(source="eleve.user.get_full_name", read_only=True)
    statut_display = serializers.CharField(source="get_statut_display", read_only=True)
    evaluation_titre = serializers.CharField(source="evaluation.titre", read_only=True)

    class Meta:
        model = Note
        fields = [
            "id",
            "evaluation",
            "evaluation_titre",
            "eleve",
            "eleve_matricule",
            "eleve_nom",
            "valeur",
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

    eleve_id = serializers.IntegerField()
    valeur = serializers.DecimalField(max_digits=5, decimal_places=2, allow_null=True)
    statut = serializers.ChoiceField(choices=Note.STATUT_CHOICES, default="presente")
    appreciation = serializers.CharField(required=False, allow_blank=True)


class BulletinListSerializer(serializers.ModelSerializer):
    """Serializer léger pour les listes de bulletins."""

    eleve_matricule = serializers.CharField(source="eleve.matricule", read_only=True)
    eleve_nom = serializers.CharField(source="eleve.user.get_full_name", read_only=True)
    classe_nom = serializers.CharField(source="classe.nom", read_only=True)
    periode_libelle = serializers.CharField(source="periode.libelle", read_only=True)
    nb_matieres_individualisees = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Bulletin
        fields = [
            "id",
            "eleve",
            "eleve_matricule",
            "eleve_nom",
            "classe",
            "classe_nom",
            "periode",
            "periode_libelle",
            "moyenne_generale",
            "rang",
            "effectif_classe",
            "decision",
            "publie",
            "signe",
            "nb_matieres_individualisees",
        ]


class BulletinDetailSerializer(serializers.ModelSerializer):
    """Serializer complet pour un bulletin."""

    eleve_matricule = serializers.CharField(source="eleve.matricule", read_only=True)
    eleve_nom = serializers.CharField(source="eleve.user.get_full_name", read_only=True)
    classe_nom = serializers.CharField(source="classe.nom", read_only=True)
    periode_libelle = serializers.CharField(source="periode.libelle", read_only=True)
    nb_matieres_individualisees = serializers.IntegerField(read_only=True, default=0)
    matieres_individuelles = serializers.SerializerMethodField()

    class Meta:
        model = Bulletin
        fields = [
            "id",
            "eleve",
            "eleve_matricule",
            "eleve_nom",
            "classe",
            "classe_nom",
            "periode",
            "periode_libelle",
            "moyenne_generale",
            "rang",
            "effectif_classe",
            "appreciation_conseil",
            "decision",
            "pdf_path",
            "nb_matieres_individualisees",
            "matieres_individuelles",
            "publie",
            "date_publication",
            "signe",
            "date_signature",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_matieres_individuelles(self, obj):
        affectations = (
            AffectationMatiereIndividuelle.objects.filter(
                eleve=obj.eleve,
                annee_scolaire=obj.classe.annee_scolaire,
            )
            .select_related("matiere", "annee_scolaire")
            .order_by("matiere__nom")
        )
        return [
            {
                "id": affectation.id,
                "matiere": affectation.matiere_id,
                "matiere_nom": affectation.matiere.nom,
                "matiere_code": affectation.matiere.code,
                "annee_scolaire": affectation.annee_scolaire_id,
                "annee_libelle": affectation.annee_scolaire.libelle,
                "coefficient": affectation.coefficient,
                "credits": affectation.credits,
                "obligatoire": affectation.obligatoire,
            }
            for affectation in affectations
        ]


class RegleValidationSerializer(serializers.ModelSerializer):
    class Meta:
        model = RegleValidation
        fields = "__all__"

    def validate_criteres(self, value):
        validate_rule_criteria(value)
        return value

    def validate(self, attrs):
        classe = attrs.get("classe", getattr(self.instance, "classe", None))
        niveau = attrs.get("niveau", getattr(self.instance, "niveau", None))
        annee = attrs.get("annee_scolaire", getattr(self.instance, "annee_scolaire", None))
        if classe and classe.annee_scolaire_id != annee.id:
            raise serializers.ValidationError({"classe": "La classe doit appartenir à l'année de la règle."})
        if classe and niveau and classe.niveau_id != niveau.id:
            raise serializers.ValidationError({"niveau": "Le niveau doit correspondre à celui de la classe."})
        return attrs
