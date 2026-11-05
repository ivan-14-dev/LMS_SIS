"""Tenant-schema configuration, separate from mutable establishment profiles."""

from django.db import models


class ModuleConfigurationBase(models.Model):
    revision = models.PositiveIntegerField(default=0)
    enabled = models.JSONField(default=dict)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

    def __str__(self):
        return f"Modules - revision {self.revision}"
