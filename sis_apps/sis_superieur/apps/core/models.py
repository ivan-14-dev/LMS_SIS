"""Models for core."""

from django.conf import settings
from django.db import models
from django.utils import timezone


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
            models.Index(fields=["app_label", "model", "object_id"]),
            models.Index(fields=["action", "created_at"]),
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
            models.Index(fields=["recipient", "is_read", "created_at"]),
        ]

    def __str__(self):
        return f"{self.recipient} - {self.title}"

    def mark_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=["is_read", "read_at"])
