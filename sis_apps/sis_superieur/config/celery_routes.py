"""Configuration du routage des files d'attente Celery - SIS Supérieur.

Sépare les tâches par file dédiée afin d'isoler les charges de travail
(webhooks entrants, publication outbox, notifications, rappels planifiés)
et de permettre un dimensionnement/scaling indépendant des workers par file.
"""

from kombu import Queue

CELERY_TASK_DEFAULT_QUEUE = "celery"

CELERY_TASK_QUEUES = (
    Queue("celery"),
    Queue("webhooks"),
    Queue("outbox"),
    Queue("notifications"),
    Queue("reminders"),
)

CELERY_TASK_ROUTES = {
    "apps.integration.tasks.process_user_webhook": {"queue": "webhooks"},
    "apps.integration.tasks.process_enrollment_webhook": {"queue": "webhooks"},
    "apps.integration.tasks.process_grade_webhook": {"queue": "webhooks"},
    "apps.integration.tasks.process_certificate_webhook": {"queue": "webhooks"},
    "apps.integration.tasks.process_cms_webhook": {"queue": "webhooks"},
    "apps.integration.tasks.process_xblock_published": {"queue": "webhooks"},
    "apps.integration.tasks.process_course_published": {"queue": "webhooks"},
    "apps.integration.tasks.publish_outbox_events": {"queue": "outbox"},
    "apps.integration.tasks.reconcile_lms": {"queue": "outbox"},
    "apps.integration.tasks.sync_all_pending_etudiants": {"queue": "outbox"},
    "apps.core.tasks.dispatch_notification_email": {"queue": "notifications"},
    "apps.core.tasks.dispatch_notification_sms": {"queue": "notifications"},
    "apps.core.tasks.dispatch_notification_webhook": {"queue": "notifications"},
    "apps.examens.tasks.emit_submission_window_reminders": {"queue": "reminders"},
    "apps.notes.tasks.emit_submission_window_reminders": {"queue": "reminders"},
}
