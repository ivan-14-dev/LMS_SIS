"""Models for core."""

from django.conf import settings
from django.db import models
from django.utils import timezone

from sis_common.complaint_models import ComplaintAttachmentBase, ComplaintBase, ComplaintEntryBase
from sis_common.delegation_models import AccessDelegationBase
from sis_common.erp_correspondence import CorrespondanceBase
from sis_common.event_models import EventInvitationBase, InstitutionalEventBase
from sis_common.hierarchy_models import (
    ConfigurationRevisionBase,
    OrganizationAttachmentBase,
    OrganizationUnitBase,
    attachment_constraint,
)
from sis_common.module_models import ModuleConfigurationBase
from sis_common.project_models import (
    PedagogicalProjectBase,
    ProjectContributionBase,
    ProjectDeliveryBase,
    ProjectEvaluationBase,
    ProjectMembershipBase,
    ProjectMilestoneBase,
    ProjectTeamBase,
)
from sis_common.signature_models import (
    ArchiveRevocationBase,
    DocumentArchiveBase,
    SignatureApprovalBase,
    SignatureMandateBase,
)
from sis_common.survey_models import InstitutionalSurveyBase, SurveyRecipientBase, SurveyResponseBase


class InstitutionalEvent(InstitutionalEventBase):
    etablissement = models.ForeignKey("etablissement.Universite", on_delete=models.PROTECT)
    salle = models.ForeignKey(
        "emplois_du_temps.Salle", on_delete=models.PROTECT, related_name="evenements_institutionnels"
    )


class EventInvitation(EventInvitationBase):
    pass


class InstitutionalSurvey(InstitutionalSurveyBase):
    etablissement = models.ForeignKey("etablissement.Universite", on_delete=models.PROTECT)


class SurveyRecipient(SurveyRecipientBase):
    pass


class SurveyResponse(SurveyResponseBase):
    pass


class PedagogicalProject(PedagogicalProjectBase):
    etablissement = models.ForeignKey("etablissement.Universite", on_delete=models.PROTECT)


class ProjectTeam(ProjectTeamBase):
    pass


class ProjectMembership(ProjectMembershipBase):
    pass


class ProjectMilestone(ProjectMilestoneBase):
    pass


class ProjectDelivery(ProjectDeliveryBase):
    pass


class ProjectEvaluation(ProjectEvaluationBase):
    pass


class ProjectContribution(ProjectContributionBase):
    pass


class SignatureApproval(SignatureApprovalBase):
    etablissement = models.ForeignKey("etablissement.Universite", on_delete=models.PROTECT)


class SignatureMandate(SignatureMandateBase):
    pass


class DocumentArchive(DocumentArchiveBase):
    etablissement = models.ForeignKey("etablissement.Universite", on_delete=models.PROTECT)


class ArchiveRevocation(ArchiveRevocationBase):
    pass


class AccessDelegation(AccessDelegationBase):
    etablissement = models.ForeignKey("etablissement.Universite", on_delete=models.PROTECT)


class ModuleConfiguration(ModuleConfigurationBase):
    etablissement = models.OneToOneField("etablissement.Universite", on_delete=models.PROTECT)


class OrganizationUnit(OrganizationUnitBase):
    etablissement = models.ForeignKey("etablissement.Universite", on_delete=models.PROTECT)

    class Meta(OrganizationUnitBase.Meta):
        abstract = False
        unique_together = [("etablissement", "code")]


class OrganizationAttachment(OrganizationAttachmentBase):
    faculty = models.OneToOneField("structure.Faculte", null=True, blank=True, on_delete=models.PROTECT)
    department = models.OneToOneField("structure.Departement", null=True, blank=True, on_delete=models.PROTECT)
    school = models.OneToOneField("structure.EcoleDoctorale", null=True, blank=True, on_delete=models.PROTECT)
    track = models.OneToOneField("formations.Parcours", null=True, blank=True, on_delete=models.PROTECT)
    teaching_unit = models.OneToOneField("ue_ecue.UE", null=True, blank=True, on_delete=models.PROTECT)
    subject = models.OneToOneField("ue_ecue.ECUE", null=True, blank=True, on_delete=models.PROTECT)
    activity = models.OneToOneField("emplois_du_temps.CreneauCours", null=True, blank=True, on_delete=models.PROTECT)

    class Meta:
        constraints = [
            attachment_constraint(
                (
                    "user",
                    "book",
                    "faculty",
                    "department",
                    "school",
                    "track",
                    "teaching_unit",
                    "subject",
                    "activity",
                )
            )
        ]


class ConfigurationRevision(ConfigurationRevisionBase):
    etablissement = models.ForeignKey("etablissement.Universite", on_delete=models.PROTECT)

    class Meta(ConfigurationRevisionBase.Meta):
        abstract = False
        unique_together = [("etablissement", "revision")]


class Reclamation(ComplaintBase):
    etablissement = models.ForeignKey("etablissement.Universite", on_delete=models.PROTECT)


class ReclamationEntry(ComplaintEntryBase):
    pass


class ReclamationPiece(ComplaintAttachmentBase):
    pass


class Correspondance(CorrespondanceBase):
    etablissement = models.ForeignKey("etablissement.Universite", on_delete=models.PROTECT)


class WorkflowEvent(models.Model):
    """Audit métier pour les transitions de workflow."""

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="workflow_events_created",
    )
    tenant_id = models.PositiveIntegerField(null=True, blank=True)
    request_id = models.CharField(max_length=64, blank=True)
    app_label = models.CharField(max_length=64)
    model = models.CharField(max_length=64)
    object_id = models.CharField(max_length=64)
    object_repr = models.CharField(max_length=255)
    action = models.CharField(max_length=64)
    title = models.CharField(max_length=255)
    message = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["app_label", "model", "object_id"], name="core_workfl_app_lab_59e6ad_idx"),
            models.Index(fields=["action", "created_at"], name="core_workfl_action_6b80c1_idx"),
        ]

    def __str__(self):
        return f"{self.title} [{self.app_label}.{self.model}:{self.object_id}]"


class WorkflowNotification(models.Model):
    """Notification liée à un événement de workflow."""

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="workflow_notifications",
    )
    event = models.ForeignKey(
        WorkflowEvent,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    category = models.CharField(max_length=64)
    title = models.CharField(max_length=255)
    message = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "is_read", "created_at"], name="core_workfl_recipie_4eb2b3_idx"),
        ]

    def __str__(self):
        return f"{self.recipient} - {self.title}"

    def mark_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=["is_read", "read_at"])
