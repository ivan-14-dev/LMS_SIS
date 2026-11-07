"""Explicit commands: no writable nested model relations or generic PATCH."""

from collections.abc import Mapping
from decimal import Decimal

from django.apps import apps
from rest_framework import serializers

from sis_common.exam_files import validate_exam_copy
from sis_common.project_competencies import CompetencyCodesField, readable_competencies
from sis_common.project_courses import course_snapshot, readable_course_snapshot

Project = apps.get_model("core", "PedagogicalProject")
Team = apps.get_model("core", "ProjectTeam")
Milestone = apps.get_model("core", "ProjectMilestone")
Delivery = apps.get_model("core", "ProjectDelivery")
Evaluation = apps.get_model("core", "ProjectEvaluation")


class CommandSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if not isinstance(data, Mapping):
            raise serializers.ValidationError({"non_field_errors": "Un objet est attendu."})
        unknown = set(data) - set(self.fields)
        if unknown:
            raise serializers.ValidationError({key: "Champ non autorisé." for key in sorted(unknown)})
        return super().to_internal_value(data)


class VersionCommand(CommandSerializer):
    version = serializers.IntegerField(min_value=1)


class ProjectCreateCommand(CommandSerializer):
    titre = serializers.CharField(max_length=200)
    description = serializers.CharField(max_length=10000, allow_blank=True, required=False, default="")
    mode = serializers.ChoiceField(choices=Project.MODES)
    responsable = serializers.IntegerField(min_value=1)
    cours = serializers.IntegerField(min_value=1, allow_null=True, required=False, default=None)
    competences = CompetencyCodesField(required=False, default=list)
    evaluateurs = serializers.ListField(
        child=serializers.IntegerField(min_value=1), max_length=50, required=False, default=list
    )


class ProjectConfigureCommand(VersionCommand):
    titre = serializers.CharField(max_length=200, required=False)
    description = serializers.CharField(max_length=10000, allow_blank=True, required=False)
    responsable = serializers.IntegerField(min_value=1, required=False)
    cours = serializers.IntegerField(min_value=1, allow_null=True, required=False)
    competences = CompetencyCodesField(required=False)
    evaluateurs = serializers.ListField(child=serializers.IntegerField(min_value=1), max_length=50, required=False)


class MembershipCommand(VersionCommand):
    membres = serializers.ListField(child=serializers.IntegerField(min_value=1), max_length=200)


class TeamCreateCommand(MembershipCommand):
    nom = serializers.CharField(max_length=120)


class MilestoneCommand(VersionCommand):
    titre = serializers.CharField(max_length=200)
    consignes = serializers.CharField(max_length=10000, allow_blank=True, required=False, default="")
    ordre = serializers.IntegerField(min_value=1, max_value=100000)
    echeance = serializers.DateTimeField()
    bareme = serializers.DecimalField(max_digits=7, decimal_places=2, min_value=Decimal("0.01"), max_value=10000)


class DeliveryCommand(VersionCommand):
    jalon = serializers.UUIDField()
    fichier = serializers.FileField(validators=[validate_exam_copy])
    commentaire = serializers.CharField(max_length=4000, allow_blank=True, required=False, default="")


class ContributionCommand(CommandSerializer):
    membre = serializers.IntegerField(min_value=1)
    note = serializers.DecimalField(max_digits=7, decimal_places=2, min_value=0, max_value=10000)
    commentaire = serializers.CharField(max_length=4000)


class EvaluationCommand(VersionCommand):
    jalon = serializers.UUIDField()
    note_groupe = serializers.DecimalField(max_digits=7, decimal_places=2, min_value=0, max_value=10000)
    commentaire = serializers.CharField(max_length=10000)
    contributions = ContributionCommand(many=True, max_length=200, required=False, default=list)


class ProjectSerializer(serializers.ModelSerializer):
    actions = serializers.SerializerMethodField()
    evaluateurs = serializers.SerializerMethodField()
    cours = serializers.SerializerMethodField()
    competences = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = [
            "id",
            "titre",
            "description",
            "mode",
            "responsable",
            "evaluateurs",
            "cours",
            "competences",
            "cree_par",
            "version",
            "created_at",
            "updated_at",
            "actions",
        ]
        read_only_fields = fields

    def get_cours(self, obj):
        return readable_course_snapshot(self.context["request"], course_snapshot(obj.cours))

    def get_competences(self, obj):
        return readable_competencies(self.context["request"], obj.competences_snapshot)

    def get_evaluateurs(self, obj):
        return list(
            obj.evaluateurs.filter(etablissement_id=obj.etablissement_id, is_active=True).values_list("pk", flat=True)
        )

    def get_actions(self, obj):
        view = self.context["view"]
        return {
            "can_manage": view.can_manage(obj),
            "can_evaluate": view.can_evaluate(obj),
            "can_submit": obj.equipes.filter(
                appartenances__membre_id=self.context["request"].user.pk,
                appartenances__retired_at__isnull=True,
            ).exists(),
        }


class TeamSerializer(serializers.ModelSerializer):
    membres = serializers.SerializerMethodField()
    actions = serializers.SerializerMethodField()

    class Meta:
        model = Team
        fields = ["id", "projet", "nom", "membres", "cree_par", "created_at", "actions"]
        read_only_fields = fields

    def get_membres(self, obj):
        memberships = obj.appartenances.filter(
            retired_at__isnull=True, membre__is_active=True, membre__etablissement_id=self.context["request"].tenant.pk
        ).select_related("membre")
        return [
            {
                "membre": item.membre_id,
                "nom": item.membre.get_full_name() or item.membre.username,
                "ajoute_par": item.ajoute_par_id,
                "created_at": item.created_at,
            }
            for item in memberships
        ]

    def get_actions(self, obj):
        view = self.context["view"]
        return {
            "can_manage": view.can_manage(obj.projet),
            "can_submit": view.is_member(obj),
            "can_evaluate": view.can_evaluate(obj.projet) and not view.is_member(obj),
        }


class MilestoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = Milestone
        fields = ["id", "projet", "titre", "consignes", "ordre", "echeance", "bareme", "cree_par", "created_at"]
        read_only_fields = fields


class DeliverySerializer(serializers.ModelSerializer):
    en_retard = serializers.SerializerMethodField()

    class Meta:
        model = Delivery
        fields = [
            "id",
            "equipe",
            "jalon",
            "revision",
            "nom",
            "taille",
            "sha256",
            "commentaire",
            "depose_par",
            "created_at",
            "en_retard",
        ]
        read_only_fields = fields

    def get_en_retard(self, obj):
        return obj.created_at > obj.jalon.echeance


class EvaluationSerializer(serializers.ModelSerializer):
    statut = serializers.SerializerMethodField()
    bareme = serializers.DecimalField(source="jalon.bareme", max_digits=7, decimal_places=2, read_only=True)
    contributions = serializers.SerializerMethodField()

    class Meta:
        model = Evaluation
        fields = [
            "id",
            "equipe",
            "jalon",
            "revision",
            "bareme",
            "note_groupe",
            "commentaire",
            "statut",
            "evalue_par",
            "created_at",
            "publie_par",
            "published_at",
            "contributions",
        ]
        read_only_fields = fields

    def get_statut(self, obj):
        return "publiee" if obj.published_at else "brouillon"

    def get_contributions(self, obj):
        rows = obj.contributions.select_related("appartenance")
        if not self.context["privileged"]:
            rows = rows.filter(appartenance__membre_id=self.context["request"].user.pk)
        return [
            {"membre": item.appartenance.membre_id, "note": str(item.note), "commentaire": item.commentaire}
            for item in rows
        ]
