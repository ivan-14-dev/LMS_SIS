"""Vérifie la configuration du routage des files Celery (SIS Secondaire & Supérieur).

Ce module de test est partagé entre les deux variantes (voir ``testpaths`` dans
``pytest.ini``) : il s'exécute avec les settings Django actifs de chaque variante
et vérifie que toutes les tâches Celery connues sont explicitement routées vers
une file dédiée (pas de file par défaut implicite pour les workloads critiques),
et que la planification Celery Beat est bien chargée.
"""

from django.conf import settings
from django.test import SimpleTestCase

EXPECTED_QUEUES = {"celery", "webhooks", "outbox", "notifications", "reminders"}

EXPECTED_ROUTED_TASKS = {
    "apps.integration.tasks.process_user_webhook": "webhooks",
    "apps.integration.tasks.process_enrollment_webhook": "webhooks",
    "apps.integration.tasks.process_grade_webhook": "webhooks",
    "apps.integration.tasks.process_certificate_webhook": "webhooks",
    "apps.integration.tasks.process_cms_webhook": "webhooks",
    "apps.integration.tasks.process_xblock_published": "webhooks",
    "apps.integration.tasks.process_course_published": "webhooks",
    "apps.integration.tasks.publish_outbox_events": "outbox",
    "apps.integration.tasks.reconcile_lms": "outbox",
    "apps.core.tasks.dispatch_notification_email": "notifications",
    "apps.core.tasks.dispatch_notification_sms": "notifications",
    "apps.core.tasks.dispatch_notification_webhook": "notifications",
    "apps.examens.tasks.emit_submission_window_reminders": "reminders",
    "apps.notes.tasks.emit_submission_window_reminders": "reminders",
}

# La tâche de synchronisation des apprenants en attente porte un nom différent
# selon la variante (élèves en secondaire, étudiants en supérieur).
EXPECTED_SYNC_PENDING_TASK_QUEUE = "outbox"

EXPECTED_BEAT_SCHEDULE_ENTRIES = {
    "publish-outbox-every-minute",
    "reconcile-lms-daily",
    "sync-pending-eleves-daily",
    "evaluation-submission-reminders-hourly",
    "exam-submission-reminders-hourly",
}


class CeleryRoutingConfigurationTests(SimpleTestCase):
    def test_all_known_queues_are_declared(self):
        declared_names = {queue.name for queue in settings.CELERY_TASK_QUEUES}
        assert EXPECTED_QUEUES <= declared_names

    def test_default_queue_is_configured(self):
        assert settings.CELERY_TASK_DEFAULT_QUEUE == "celery"

    def test_webhook_outbox_notification_and_reminder_tasks_are_routed(self):
        for task_name, expected_queue in EXPECTED_ROUTED_TASKS.items():
            assert task_name in settings.CELERY_TASK_ROUTES, f"{task_name} n'est pas routée"
            assert settings.CELERY_TASK_ROUTES[task_name]["queue"] == expected_queue

    def test_sync_pending_learners_task_is_routed_to_outbox_queue(self):
        sync_pending_routes = [
            route
            for task_name, route in settings.CELERY_TASK_ROUTES.items()
            if task_name.startswith("apps.integration.tasks.sync_all_pending_")
        ]
        assert sync_pending_routes, "Aucune tâche sync_all_pending_* routée"
        for route in sync_pending_routes:
            assert route["queue"] == EXPECTED_SYNC_PENDING_TASK_QUEUE

    def test_celery_beat_schedule_is_loaded(self):
        assert EXPECTED_BEAT_SCHEDULE_ENTRIES <= set(settings.CELERY_BEAT_SCHEDULE.keys())
