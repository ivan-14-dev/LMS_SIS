import uuid

from django.db import models


class WorkspaceInstitutionFields(models.Model):
    workspace_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    workspace_peer = models.UUIDField(null=True, blank=True, editable=False)
    workspace_home = models.UUIDField(null=True, blank=True, editable=False)
    workspace_revision = models.PositiveIntegerField(default=0, editable=False)

    class Meta:
        abstract = True
