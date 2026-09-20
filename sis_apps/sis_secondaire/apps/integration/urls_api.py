"""URLs API for integration (SIS Secondaire)."""

from django.urls import path

from . import api

app_name = "integration_api"

urlpatterns = [
    # Webhooks entrants
    path("webhook/lms/", api.webhook_lms, name="webhook-lms"),
    path("webhook/cms/", api.webhook_cms, name="webhook-cms"),
    # Status & santé
    path("sync/status/", api.sync_status, name="sync-status"),
    path("health/", api.health, name="health"),
    path("mappings/users/", api.user_mappings, name="user-mappings"),
    path("mappings/courses/", api.course_mappings, name="course-mappings"),
    path("outbox/", api.outbox_events, name="outbox-events"),
    # Synchronisations
    path("sync/user/<int:user_id>/", api.sync_user, name="sync-user"),
    path("sync/course/", api.sync_course, name="sync-course"),
    path("sync/enroll/", api.sync_enroll, name="sync-enroll"),
    path("sync/grade/", api.sync_grade, name="sync-grade"),
    path("sync/certificate/", api.sync_certificate, name="sync-certificate"),
]
