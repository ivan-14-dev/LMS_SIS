"""Tâches Celery d'intégration LMS + CMS - SIS Supérieur."""

import logging

from celery import shared_task
from django.utils import timezone

from .models import EdxCourseMapping, EdxEnrollment, EdxUserMapping, OutboxEvent
from .sync_service import SyncService

logger = logging.getLogger(__name__)


def _process_webhook(event_type, payload):
    from apps.etudiants.models import Etudiant
    from apps.notes.models import Note

    from .models import EdxGradeLog
    from .webhook_handlers import WebhookHandler

    handler = WebhookHandler(
        EdxUserMapping, EdxCourseMapping, EdxEnrollment, EdxGradeLog, Etudiant, Note
    )
    if not handler.handle(event_type, payload):
        raise ValueError(f"Webhook processing failed for {event_type}")
    return True


@shared_task(autoretry_for=(Exception,), retry_backoff=True, max_retries=5)
def process_user_webhook(event_type, payload):
    return _process_webhook(event_type, payload)


@shared_task(autoretry_for=(Exception,), retry_backoff=True, max_retries=5)
def process_enrollment_webhook(event_type, payload):
    return _process_webhook(event_type, payload)


@shared_task(autoretry_for=(Exception,), retry_backoff=True, max_retries=5)
def process_grade_webhook(event_type, payload):
    return _process_webhook(event_type, payload)


@shared_task(autoretry_for=(Exception,), retry_backoff=True, max_retries=5)
def process_certificate_webhook(event_type, payload):
    return _process_webhook(event_type, payload)


@shared_task(autoretry_for=(Exception,), retry_backoff=True, max_retries=5)
def process_cms_webhook(event_type, payload):
    return _process_webhook(event_type, payload)


@shared_task
def process_xblock_published(payload):
    """Webhook CMS : XBlock modifié dans Studio."""
    logger.info(f"XBlock updated in Studio: {payload.get('block_id')}")


@shared_task
def process_course_published(payload):
    """Webhook CMS : cours publié dans Studio."""
    logger.info(f"Course published in CMS: {payload.get('course_key')}")


@shared_task
def publish_outbox_events():
    pending = OutboxEvent.objects.filter(statut="pending")[:100]
    for event in pending:
        try:
            event.statut = "processing"
            event.save()
            event.statut = "done"
            event.derniere_tentative = timezone.now()
            event.save()
        except Exception as e:
            event.nb_tentatives += 1
            event.erreur = str(e)
            if event.nb_tentatives >= 5:
                event.statut = "dead"
            else:
                event.statut = "pending"
            event.save()


@shared_task
def reconcile_lms():
    logger.info("Starting LMS reconciliation (Supérieur)")
    service = SyncService()
    for enrollment in EdxEnrollment.objects.filter(is_active=True)[:500]:
        try:
            course = enrollment.course
            user_map = EdxUserMapping.objects.get(user_sis=enrollment.etudiant.user)
            grades = service.client.get_grades(course.course_id, user_map.username_edx)
            enrollment.progression = min(
                max(float(grades.get("percent", 0)) * 100, 0), 100
            )
            enrollment.last_sync = timezone.now()
            enrollment.save()
        except Exception as e:
            logger.warning(f"Reconcile error: {e}")


@shared_task
def sync_all_pending_etudiants():
    from apps.etudiants.models import Etudiant

    service = SyncService()
    pending = Etudiant.objects.exclude(
        user__edx_mapping_u__isnull=False
    ).select_related("user")[:200]
    count = 0
    for etu in pending:
        try:
            service.sync_user_to_lms(etu.user, role="student")
            count += 1
        except Exception as e:
            logger.error(f"Failed to sync etudiant {etu.id}: {e}")
    logger.info(f"Synced {count} etudiants to LMS")
