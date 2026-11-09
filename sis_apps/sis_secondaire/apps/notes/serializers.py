"""Serializers for notes (SIS Secondaire)."""

from apps.classes.models import ProgrammeMatiere
from apps.eleves.models import AffectationMatiereIndividuelle
from rest_framework import serializers

from sis_common.academic_configuration import validate_rule_criteria
from sis_common.authorization import user_has_any_role
from sis_common.grade_entry import GradeUpdateSerializerMixin, validate_assessment_scale
from sis_common.learning_offerings import ModelValidationSerializerMixin
from sis_common.serializers import TenantBoundSerializerMixin
from sis_common.submission_windows import get_submission_window_alert, get_submission_window_status

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
    soumission_statut = serializers.SerializerMethodField()
    soumission_alerte = serializers.SerializerMethodField()

    class Meta:
        model = Evaluation
        fields = [
            "id",
            "offre_configuration",
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
            "debut_soumission",
            "fin_soumission",
            "debut_soumission",
            "fin_soumission",
            "bareme",
            "coefficient",
            "ponderation",
            "eleve_cible",
            "eleve_cible_matricule",
            "eleve_cible_nom",
            "individualisee",
            "nb_notes",
            "notes_saisies",
            "soumission_statut",
            "soumission_alerte",
            "enseignant_nom",
        ]

    def get_individualisee(self, obj):
        return bool(obj.eleve_cible_id)

    def get_nb_notes(self, obj):
        return obj.notes.exclude(valeur__isnull=True, resultat={}).count()

    def get_notes_saisies(self, obj):
        return self.get_nb_notes(obj) > 0

    def get_soumission_statut(self, obj):
        return get_submission_window_status(obj)

    def get_soumission_alerte(self, obj):
        request = self.context.get("request")
        configuration = getattr(getattr(request, "tenant", None), "configuration_academique", {})
        return get_submission_window_alert(obj, configuration, "evaluation")


class EvaluationDetailSerializer(
    ModelValidationSerializerMixin, TenantBoundSerializerMixin, serializers.ModelSerializer
):
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
    soumission_statut = serializers.SerializerMethodField()
    soumission_alerte = serializers.SerializerMethodField()

    class Meta:
        model = Evaluation
        fields = [
            "id",
            "offre_configuration",
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
            "debut_soumission",
            "fin_soumission",
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
            "soumission_statut",
            "soumission_alerte",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_nb_notes(self, obj):
        return obj.notes.exclude(valeur__isnull=True, resultat={}).count()

    def get_individualisee(self, obj):
        return bool(obj.eleve_cible_id)

    def get_soumission_statut(self, obj):
        return get_submission_window_status(obj)

    def get_soumission_alerte(self, obj):
        request = self.context.get("request")
        configuration = getattr(getattr(request, "tenant", None), "configuration_academique", {})
        return get_submission_window_alert(obj, configuration, "evaluation")

    def validate(self, attrs):
        attrs = super().validate(attrs)
        validate_assessment_scale(attrs, self.instance)
        classe = attrs.get("classe", getattr(self.instance, "classe", None))
        matiere = attrs.get("matiere", getattr(self.instance, "matiere", None))
        periode = attrs.get("periode", getattr(self.instance, "periode", None))
        enseignant = attrs.get("enseignant", getattr(self.instance, "enseignant", None))
        if classe and periode and classe.annee_scolaire_id != periode.annee_scolaire_id:
            raise serializers.ValidationError({"periode": "La période doit appartenir à l'année de la classe."})
        request = self.context.get("request")
        tenant = getattr(request, "tenant", None)
        if tenant and periode and periode.annee_scolaire.etablissement_id != tenant.pk:
            raise serializers.ValidationError({"periode": "Cette période appartient à un autre établissement."})
        date = attrs.get("date", getattr(self.instance, "date", None))
        if date and periode and not periode.date_debut <= date <= periode.date_fin:
            raise serializers.ValidationError({"date": "La date doit appartenir à la période de l'évaluation."})
        user = getattr(request, "user", None)
        if user and not user.is_superuser and user_has_any_role(user, ("enseignant",)):
            if enseignant and enseignant.user_id != user.pk:
                raise serializers.ValidationError(
                    {"enseignant": "Vous ne pouvez créer une évaluation pour un autre enseignant."}
                )
        eleve_cible = attrs.get("eleve_cible", getattr(self.instance, "eleve_cible", None))
        debut_soumission = attrs.get("debut_soumission", getattr(self.instance, "debut_soumission", None))
        fin_soumission = attrs.get("fin_soumission", getattr(self.instance, "fin_soumission", None))
        if debut_soumission and fin_soumission and fin_soumission < debut_soumission:
            raise serializers.ValidationError(
                {"fin_soumission": "La fin de soumission doit être postérieure au début."}
            )
        if not eleve_cible:
            return attrs
        class_member = (
            eleve_cible.classe_actuelle_id == getattr(classe, "id", None)
            or classe.inscriptions.filter(
                eleve=eleve_cible,
                statut__in=("en_cours", "validee"),
            ).exists()
        )
        if not class_member:
            raise serializers.ValidationError(
                {"eleve_cible": "L'élève ciblé doit appartenir à la classe de l'évaluation."}
            )
        subject_in_program = ProgrammeMatiere.objects.filter(classe=classe, matiere=matiere).exists()
        if (
            not subject_in_program
            and not AffectationMatiereIndividuelle.objects.filter(
                eleve=eleve_cible,
                annee_scolaire=classe.annee_scolaire,
                matiere=matiere,
            ).exists()
        ):
            raise serializers.ValidationError(
                {
                    "eleve_cible": (
                        "L'élève ciblé doit avoir cette matière dans son programme de classe "
                        "ou via une affectation individuelle."
                    )
                }
            )
        return attrs


class NoteSerializer(ModelValidationSerializerMixin, GradeUpdateSerializerMixin, serializers.ModelSerializer):
    """Serializer pour les notes."""

    eleve_matricule = serializers.CharField(source="eleve.matricule", read_only=True)
    eleve_nom = serializers.CharField(source="eleve.user.get_full_name", read_only=True)
    statut_display = serializers.CharField(source="get_statut_display", read_only=True)
    evaluation_titre = serializers.CharField(source="evaluation.titre", read_only=True)
    bareme = serializers.DecimalField(source="evaluation.bareme", max_digits=5, decimal_places=2, read_only=True)

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
            "bareme",
            "resultat",
            "resultat_offre",
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
    resultat = serializers.JSONField(required=False, default=dict)
    statut = serializers.ChoiceField(choices=Note.STATUT_CHOICES, default="presente")
    appreciation = serializers.CharField(required=False, allow_blank=True)


class BulletinRevisionMixin:
    def get_rectification_publiee(self, obj):
        return Bulletin.objects.filter(rectifie=obj, publie=True).values_list("pk", flat=True).first()


class BulletinListSerializer(BulletinRevisionMixin, serializers.ModelSerializer):
    """Serializer léger pour les listes de bulletins."""

    eleve_matricule = serializers.CharField(source="eleve.matricule", read_only=True)
    eleve_nom = serializers.CharField(source="eleve.user.get_full_name", read_only=True)
    classe_nom = serializers.CharField(source="classe.nom", read_only=True)
    periode_libelle = serializers.CharField(source="periode.libelle", read_only=True)
    nb_matieres_individualisees = serializers.IntegerField(read_only=True, default=0)
    calcule = serializers.SerializerMethodField()
    rectification_publiee = serializers.SerializerMethodField()

    def get_calcule(self, obj):
        return bool(obj.calcul_detail)

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
            "calcule",
            "date_validation",
            "revision",
            "rectifie",
            "rectification_publiee",
        ]


class BulletinDetailSerializer(BulletinRevisionMixin, serializers.ModelSerializer):
    """Serializer complet pour un bulletin."""

    eleve_matricule = serializers.CharField(source="eleve.matricule", read_only=True)
    eleve_nom = serializers.CharField(source="eleve.user.get_full_name", read_only=True)
    classe_nom = serializers.CharField(source="classe.nom", read_only=True)
    periode_libelle = serializers.CharField(source="periode.libelle", read_only=True)
    nb_matieres_individualisees = serializers.IntegerField(read_only=True, default=0)
    matieres_individuelles = serializers.SerializerMethodField()
    rectification_publiee = serializers.SerializerMethodField()

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
            "calcul_detail",
            "valide_par",
            "date_validation",
            "revision",
            "rectifie",
            "motif_rectification",
            "rectification_demandee_par",
            "rectification_publiee",
        ]
        read_only_fields = [
            "id", "created_at", "updated_at", "calcul_detail", "valide_par", "date_validation",
            "revision", "rectifie", "motif_rectification", "rectification_demandee_par",
        ]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        existing = Bulletin.objects.filter(
            eleve=attrs.get("eleve", getattr(self.instance, "eleve_id", None)),
            periode=attrs.get("periode", getattr(self.instance, "periode_id", None)),
        )
        if self.instance:
            existing = existing.exclude(pk=self.instance.pk)
        if existing.exists():
            raise serializers.ValidationError(
                {"bulletin": "Un bulletin existe déjà. Utilisez son circuit de rectification."}
            )
        return attrs

    def get_matieres_individuelles(self, obj):
        if obj.calcul_detail:
            return []
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
