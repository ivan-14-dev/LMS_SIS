"""URLs API for integration (SIS Supérieur)."""

from django.urls import path

from sis_common.lms_user_candidates import user_candidates

from . import api

app_name = "integration_api"

urlpatterns = [
    path("webhook/lms/", api.webhook_lms, name="webhook-lms"),
    path("webhook/cms/", api.webhook_cms, name="webhook-cms"),
    path("sync/status/", api.sync_status, name="sync-status"),
    path("health/", api.health, name="health"),
    path("mappings/users/", api.user_mappings, name="user-mappings"),
    path("mappings/users/candidates/", user_candidates, name="user-candidates"),
    path("mappings/courses/", api.course_mappings, name="course-mappings"),
    path("outbox/", api.outbox_events, name="outbox-events"),
    path("outbox/process/", api.process_outbox, name="process-outbox"),
    path("sync/user/<int:user_id>/", api.sync_user, name="sync-user"),
    path("sync/course/", api.sync_course, name="sync-course"),
    path("sync/course/<int:mapping_id>/publication/", api.publish_course, name="course-publication"),
    path(
        "sync/course-live/<int:mapping_id>/",
        api.sync_course_live,
        name="sync-course-live",
    ),
    path("sync/enroll/", api.sync_enroll, name="sync-enroll"),
    path("sync/teaching/", api.sync_teaching, name="sync-teaching"),
    path("sync/grade/", api.sync_grade, name="sync-grade"),
    path("sync/certificate/", api.sync_certificate, name="sync-certificate"),
]
