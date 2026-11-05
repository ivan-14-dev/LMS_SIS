import uuid

from django.conf import settings
from django.db import models


class ManagedAccount(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="sis_binding")
    manager = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="sis_managed_accounts")
    username = models.CharField(max_length=30, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        permissions = [("provision_accounts", "Provision explicitly managed SIS accounts")]


class ManagedCourse(models.Model):
    course_id = models.CharField(max_length=200, unique=True)
    manager = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="sis_managed_courses")
    ownership_token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    initialized = models.BooleanField(default=False)
    adopted = models.BooleanField(default=False, db_default=False)
    revoked = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        permissions = [("provision_courses", "Provision explicitly managed SIS courses")]


class ManagedAccess(models.Model):
    course = models.ForeignKey(ManagedCourse, on_delete=models.PROTECT)
    account = models.ForeignKey(ManagedAccount, on_delete=models.PROTECT)
    kind = models.CharField(max_length=16, choices=[("enrollment", "Enrollment"), ("teaching", "Course staff")])
    is_active = models.BooleanField(default=False)
    requested_at = models.DateTimeField()
    initialized = models.BooleanField(default=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["course", "account", "kind"], name="unique_sis_course_access")]
        permissions = [
            ("manage_enrollments", "Manage enrollments of owned accounts in owned courses"),
            ("manage_teaching", "Manage course staff assignments of owned accounts in owned courses"),
        ]


class ManagedPublication(models.Model):
    operation_id = models.UUIDField(primary_key=True)
    course = models.ForeignKey(ManagedCourse, on_delete=models.PROTECT)
    revision = models.CharField(max_length=24)
    published_version = models.CharField(max_length=24, blank=True)

    class Meta:
        permissions = [("publish_courses", "Publish explicitly reviewed revisions of owned courses")]
