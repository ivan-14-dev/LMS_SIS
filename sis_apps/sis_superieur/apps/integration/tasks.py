"""Tâches Celery d'intégration LMS + CMS - SIS Supérieur."""

import logging

from celery import shared_task
from django.db import transaction
from django.utils import timezone
from django_tenants.utils import get_tenant_model, schema_context

from .models import EdxCourseMapping, EdxEnrollment, EdxUserMapping, OutboxEvent
from .sync_service import SyncService

logger = logging.getLogger(__name__)

OUTBOX_MAX_ATTEMPTS = 5


def _iter_tenant_schemas():
    """Liste les schémas des universités (hors ``public``) à traiter."""
    TenantModel = get_tenant_model()
    return list(
        TenantModel.objects.exclude(schema_name="public").values_list(
            "schema_name", flat=True
        )
    )


def _process_webhook(event_type, payload, schema_name):
    from apps.etudiants.models import Etudiant
    from apps.notes.models import Note

    from .models import EdxGradeLog
    from .webhook_handlers import WebhookHandler

    with schema_context(schema_name):
        handler = WebhookHandler(
            EdxUserMapping,
            EdxCourseMapping,
            EdxEnrollment,
            EdxGradeLog,
            Etudiant,
            Note,
        )
        if not handler.handle(event_type, payload):
            raise ValueError(f"Webhook processing failed for {event_type}")
    return True


@shared_task(autoretry_for=(Exception,), retry_backoff=True, max_retries=5)
def process_user_webhook(event_type, payload, schema_name):
    return _process_webhook(event_type, payload, schema_name)


@shared_task(autoretry_for=(Exception,), retry_backoff=True, max_retries=5)
def process_enrollment_webhook(event_type, payload, schema_name):
    return _process_webhook(event_type, payload, schema_name)


@shared_task(autoretry_for=(Exception,), retry_backoff=True, max_retries=5)
def process_grade_webhook(event_type, payload, schema_name):
    return _process_webhook(event_type, payload, schema_name)


@shared_task(autoretry_for=(Exception,), retry_backoff=True, max_retries=5)
def process_certificate_webhook(event_type, payload, schema_name):
    return _process_webhook(event_type, payload, schema_name)


@shared_task(autoretry_for=(Exception,), retry_backoff=True, max_retries=5)
def process_cms_webhook(event_type, payload, schema_name):
    return _process_webhook(event_type, payload, schema_name)


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
    """Publie les événements en attente pour chaque université.

    Chaque événement échoué est rejoué via le même appel de synchronisation
    LMS/CMS qui l'a initialement mis en échec (voir ``sync_service.py``) :
    l'échec n'est donc plus silencieusement marqué comme traité. Après
    ``OUTBOX_MAX_ATTEMPTS`` tentatives, l'événement passe en ``dead`` (file
    d'échec) au lieu d'être retenté indéfiniment.
    """
    total = 0
    for schema_name in _iter_tenant_schemas():
        with schema_context(schema_name):
            total += _publish_outbox_events_for_current_schema()
    return total


def _retry_user_sync(service, event):
    from apps.utilisateurs.models import Utilisateur

    user = Utilisateur.objects.get(pk=event.aggregate_id)
    role = event.payload.get("role", "student")
    service.sync_user_to_lms(user, role=role)


def _retry_course_create(service, event):
    from apps.etablissement.models import AnneeUniversitaire
    from apps.ue_ecue.models import ECUE

    ecue = ECUE.objects.get(pk=event.aggregate_id)
    annee_universitaire = AnneeUniversitaire.objects.get(
        pk=event.payload["annee_universitaire_id"]
    )
    display_name = event.payload.get("display_name") or str(ecue)
    service.sync_course_to_cms(ecue, annee_universitaire, display_name)


def _retry_enrollment_create(service, event):
    from apps.etudiants.models import Etudiant

    etudiant = Etudiant.objects.get(pk=event.aggregate_id)
    course_mapping = EdxCourseMapping.objects.get(pk=event.payload["course_mapping_id"])
    mode = event.payload.get("mode", "audit")
    service.sync_enrollment_to_lms(etudiant, course_mapping, mode=mode)


OUTBOX_HANDLERS = {
    "user.sync": _retry_user_sync,
    "course.create": _retry_course_create,
    "enrollment.create": _retry_enrollment_create,
}


def _claim_pending_outbox_events(batch_size=100):
    """Verrouille un lot d'événements ``pending`` et les passe en ``processing``.

    ``select_for_update(skip_locked=True)`` garantit qu'aucun autre worker
    Celery ne peut réclamer les mêmes lignes en parallèle, et la transaction
    est validée avant tout appel réseau vers le LMS pour ne pas garder les
    verrous plus longtemps que nécessaire.
    """
    with transaction.atomic():
        ids = list(
            OutboxEvent.objects.select_for_update(skip_locked=True)
            .filter(statut="pending")
            .order_by("created_at")
            .values_list("id", flat=True)[:batch_size]
        )
        if ids:
            OutboxEvent.objects.filter(id__in=ids).update(
                statut="processing", derniere_tentative=timezone.now()
            )
    return list(OutboxEvent.objects.filter(id__in=ids)) if ids else []


def _publish_outbox_events_for_current_schema():
    events = _claim_pending_outbox_events()
    if not events:
        return 0
    # Le rejeu réutilise les méthodes de synchronisation réelles ; il désactive
    # leur ré-enfilage automatique en cas d'échec puisque cette tâche gère
    # elle-même les tentatives/l'état terminal (dead letter) de l'événement.
    service = SyncService(enqueue_failures=False)
    for event in events:
        handler = OUTBOX_HANDLERS.get(event.event_type)
        try:
            if handler is None:
                raise ValueError(f"Type d'événement outbox inconnu: {event.event_type}")
            handler(service, event)
        except Exception as e:
            event.nb_tentatives += 1
            event.erreur = str(e)
            event.statut = (
                "dead" if event.nb_tentatives >= OUTBOX_MAX_ATTEMPTS else "pending"
            )
            event.save(update_fields=["nb_tentatives", "erreur", "statut"])
            logger.warning(f"Outbox event {event.id} ({event.event_type}) failed: {e}")
        else:
            event.statut = "done"
            event.save(update_fields=["statut"])
    return len(events)


@shared_task
def reconcile_lms():
    logger.info("Starting LMS reconciliation (Supérieur)")
    for schema_name in _iter_tenant_schemas():
        with schema_context(schema_name):
            _reconcile_lms_for_current_schema()


def _reconcile_lms_for_current_schema():
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
    total = 0
    for schema_name in _iter_tenant_schemas():
        with schema_context(schema_name):
            total += _sync_all_pending_etudiants_for_current_schema()
    logger.info(f"Synced {total} etudiants to LMS")


def _sync_all_pending_etudiants_for_current_schema():
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
    return count
