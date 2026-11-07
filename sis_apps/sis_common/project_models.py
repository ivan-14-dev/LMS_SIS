"""Private pedagogical projects, independent of research and official SIS grades."""

import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q

from sis_common.exam_files import PrivateExamStorage, validate_exam_copy


def project_delivery_path(instance, filename):
    project = instance.equipe.projet
    return f"projets/{project.etablissement_id}/{project.pk}/{instance.equipe_id}/{uuid.uuid4().hex}.pdf"


class PedagogicalProjectBase(models.Model):
    MODES = [("individuel", "Individuel"), ("collectif", "Collectif")]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    titre = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    mode = models.CharField(max_length=12, choices=MODES)
    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="projets_pedagogiques"
    )
    evaluateurs = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name="projets_a_evaluer", blank=True)
    cours = models.ForeignKey(
        "integration.EdxCourseMapping", on_delete=models.PROTECT, related_name="projets", null=True, blank=True
    )
    competences_snapshot = models.JSONField(default=None, null=True, blank=True, editable=False)
    cree_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ["-updated_at", "id"]
        permissions = [
            ("gerer_projet_pedagogique", "Organiser les projets pédagogiques et leurs équipes"),
            ("evaluer_projet_pedagogique", "Évaluer les projets pédagogiques explicitement confiés"),
        ]
        constraints = [models.CheckConstraint(condition=Q(mode__in=["individuel", "collectif"]), name="project_mode")]

    def __str__(self):
        return f"PRJ-{self.pk}"


class ProjectTeamBase(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    projet = models.ForeignKey("core.PedagogicalProject", on_delete=models.PROTECT, related_name="equipes")
    nom = models.CharField(max_length=120)
    cree_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True
        ordering = ["created_at", "id"]
        constraints = [models.UniqueConstraint(fields=["projet", "nom"], name="project_team_name")]


class ProjectMembershipBase(models.Model):
    equipe = models.ForeignKey("core.ProjectTeam", on_delete=models.PROTECT, related_name="appartenances")
    membre = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    ajoute_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    retire_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+", null=True, blank=True
    )
    retired_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True
        ordering = ["created_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["equipe", "membre"], condition=Q(retired_at__isnull=True), name="project_active_member"
            ),
            models.CheckConstraint(
                condition=(
                    Q(retired_at__isnull=True, retire_par__isnull=True)
                    | Q(retired_at__isnull=False, retire_par__isnull=False)
                ),
                name="project_retirement_actor",
            ),
        ]


class ProjectMilestoneBase(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    projet = models.ForeignKey("core.PedagogicalProject", on_delete=models.PROTECT, related_name="jalons")
    titre = models.CharField(max_length=200)
    consignes = models.TextField(blank=True)
    ordre = models.PositiveIntegerField()
    echeance = models.DateTimeField()
    bareme = models.DecimalField(max_digits=7, decimal_places=2)
    cree_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True
        ordering = ["ordre", "id"]
        constraints = [
            models.UniqueConstraint(fields=["projet", "ordre"], name="project_milestone_order"),
            models.CheckConstraint(condition=Q(bareme__gt=0, bareme__lte=10000), name="project_positive_scale"),
            models.CheckConstraint(condition=Q(ordre__gte=1), name="project_positive_order"),
        ]


class ProjectDeliveryBase(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    equipe = models.ForeignKey("core.ProjectTeam", on_delete=models.PROTECT, related_name="livrables")
    jalon = models.ForeignKey("core.ProjectMilestone", on_delete=models.PROTECT, related_name="livrables")
    revision = models.PositiveIntegerField()
    fichier = models.FileField(
        storage=PrivateExamStorage(), upload_to=project_delivery_path, validators=[validate_exam_copy], max_length=255
    )
    nom = models.CharField(max_length=200)
    taille = models.PositiveIntegerField()
    sha256 = models.CharField(max_length=64)
    commentaire = models.TextField(blank=True)
    depose_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True
        ordering = ["-created_at", "id"]
        constraints = [
            models.UniqueConstraint(fields=["equipe", "jalon", "revision"], name="project_delivery_revision"),
        ]


class ProjectEvaluationBase(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    equipe = models.ForeignKey("core.ProjectTeam", on_delete=models.PROTECT, related_name="evaluations")
    jalon = models.ForeignKey("core.ProjectMilestone", on_delete=models.PROTECT, related_name="evaluations")
    revision = models.PositiveIntegerField()
    note_groupe = models.DecimalField(max_digits=7, decimal_places=2)
    commentaire = models.TextField()
    evalue_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    publie_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+", null=True, blank=True
    )
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True
        ordering = ["-created_at", "id"]
        constraints = [
            models.UniqueConstraint(fields=["equipe", "jalon", "revision"], name="project_evaluation_revision"),
            models.CheckConstraint(condition=Q(note_groupe__gte=0), name="project_group_score_nonnegative"),
            models.CheckConstraint(
                condition=(
                    Q(published_at__isnull=True, publie_par__isnull=True)
                    | Q(published_at__isnull=False, publie_par__isnull=False)
                ),
                name="project_publication_actor",
            ),
        ]


class ProjectContributionBase(models.Model):
    evaluation = models.ForeignKey("core.ProjectEvaluation", on_delete=models.PROTECT, related_name="contributions")
    appartenance = models.ForeignKey("core.ProjectMembership", on_delete=models.PROTECT, related_name="+")
    note = models.DecimalField(max_digits=7, decimal_places=2)
    commentaire = models.TextField()

    class Meta:
        abstract = True
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(fields=["evaluation", "appartenance"], name="project_contribution_member"),
            models.CheckConstraint(condition=Q(note__gte=0), name="project_individual_score_nonnegative"),
        ]
