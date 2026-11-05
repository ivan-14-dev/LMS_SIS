"""Tâches Celery d'intégration LMS + CMS - SIS Secondaire."""

import logging

from celery import shared_task
from django.db import transaction
from django.utils import timezone
from django_tenants.utils import get_tenant_model, schema_context

from sis_common.lms_access_sync import (
    access_retry_ready,
    permanent_access_failure,
    queue_revoked_access,
    recover_interrupted_access,
    replay_access,
    save_claimed_outbox_event,
)
from sis_common.lms_outbox import publish_tenant_outbox

from .models import EdxCourseMapping, EdxEnrollment, EdxUserMapping, OutboxEvent
from .sync_service import SyncService

logger = logging.getLogger(__name__)

OUTBOX_MAX_ATTEMPTS = 5


def _iter_tenant_schemas():
    """Liste les schémas des établissements (hors ``public``) à traiter."""
    TenantModel = get_tenant_model()
    return list(TenantModel.objects.exclude(schema_name="public").values_list("schema_name", flat=True))


def _process_webhook(event_type, payload, schema_name):
    from apps.eleves.models import Eleve
    from apps.notes.models import Note

    from .models import EdxGradeLog
    from .webhook_handlers import WebhookHandler

    with schema_context(schema_name):
        handler = WebhookHandler(
            EdxUserMapping,
            EdxCourseMapping,
            EdxEnrollment,
            EdxGradeLog,
            Eleve,
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
    logger.info(f"Course published: {payload.get('course_key')}")


# ============== Outbox publisher ==============


def _retry_user_sync(service, event):
    from apps.utilisateurs.models import Utilisateur

    user = Utilisateur.objects.get(pk=event.aggregate_id)
    role = event.payload.get("role", "student")
    service.sync_user_to_lms(user, role=role)


def _retry_course_create(service, event):
    from apps.classes.models import Classe, Matiere

    matiere = Matiere.objects.get(pk=event.aggregate_id)
    classe = Classe.objects.get(pk=event.payload["classe_id"])
    display_name = event.payload.get("display_name") or str(matiere)
    service.sync_course_to_cms(
        matiere, classe, display_name, requested_at=event.payload.get("requested_at", event.created_at)
    )


def _retry_enrollment_create(service, event):
    from apps.eleves.models import Eleve

    eleve = Eleve.objects.get(pk=event.aggregate_id)
    course_mapping = EdxCourseMapping.objects.get(pk=event.payload["course_mapping_id"])
    mode = event.payload.get("mode", "audit")
    service.sync_enrollment_to_lms(eleve, course_mapping, mode=mode, requested_at=event.created_at)


OUTBOX_HANDLERS = {
    "access.set": replay_access,
    "user.sync": _retry_user_sync,
    "course.create": _retry_course_create,
    "enrollment.create": _retry_enrollment_create,
}


def _claim_pending_outbox_events(batch_size=100, excluded_ids=()):
    """Verrouille un lot d'événements ``pending`` et les passe en ``processing``.

    ``select_for_update(skip_locked=True)`` garantit qu'aucun autre worker
    Celery ne peut réclamer les mêmes lignes en parallèle (plusieurs
    exécutions concurrentes de ``publish_outbox_events`` ne se marchent donc
    pas dessus), et la transaction est validée avant tout appel réseau vers le
    LMS pour ne pas garder les verrous plus longtemps que nécessaire.
    """
    with transaction.atomic():
        ids = list(
            OutboxEvent.objects.select_for_update(skip_locked=True)
            .filter(access_retry_ready(), statut="pending")
            .exclude(pk__in=excluded_ids)
            .order_by("created_at")
            .values_list("id", flat=True)[:batch_size]
        )
        if ids:
            OutboxEvent.objects.filter(id__in=ids).update(statut="processing", derniere_tentative=timezone.now())
    return list(OutboxEvent.objects.filter(id__in=ids)) if ids else []


def _publish_outbox_events_for_current_schema():
    recover_interrupted_access()
    queue_revoked_access()
    processed = []
    service = None
    # Une réservation par appel évite d'expirer un lot attendant des I/O précédentes.
    while len(processed) < 100:
        events = _claim_pending_outbox_events(batch_size=1, excluded_ids=processed)
        if not events:
            break
        event = events[0]
        processed.append(event.pk)
        if service is None:
            service = SyncService(enqueue_failures=False)
        handler = OUTBOX_HANDLERS.get(event.event_type)
        try:
            if handler is None:
                raise ValueError(f"Type d'événement outbox inconnu: {event.event_type}")
            handler(service, event)
        except Exception as e:
            event.nb_tentatives = min(event.nb_tentatives + 1, 32767)
            event.erreur = str(e)
            permanent = event.event_type in ("access.set", "enrollment.create") and permanent_access_failure(e)
            exhausted = event.event_type != "access.set" and event.nb_tentatives >= OUTBOX_MAX_ATTEMPTS
            event.statut = "dead" if permanent or exhausted else "pending"
            logger.warning(f"Outbox event {event.id} ({event.event_type}) failed: {e}")
        else:
            event.statut = "done"
        save_claimed_outbox_event(event)
    return len(processed)


@shared_task
def publish_outbox_events():
    """Publie les événements en attente pour chaque établissement.

    Chaque événement échoué est rejoué via le même appel de synchronisation
    LMS/CMS qui l'a initialement mis en échec (voir ``sync_service.py``) :
    l'échec n'est donc plus silencieusement marqué comme traité. Après
    ``OUTBOX_MAX_ATTEMPTS`` tentatives, les événements historiques passent en
    ``dead``. Les décisions d'accès continuent avec backoff après une erreur
    transitoire, afin qu'un retrait ne soit jamais abandonné après une panne.
    """
    total = 0
    for schema_name in _iter_tenant_schemas():
        with schema_context(schema_name):
            total += _publish_outbox_events_for_current_schema()
    return total


@shared_task(queue="outbox")
def publish_tenant_outbox_events(tenant_id, schema_name):
    """Process one institution using the same durable, bounded publisher as Beat."""
    return publish_tenant_outbox(tenant_id, schema_name, _publish_outbox_events_for_current_schema)


# ============== Réconciliation ==============


def _reconcile_lms_for_current_schema():
    service = SyncService()
    for enrollment in EdxEnrollment.objects.filter(is_active=True)[:500]:
        try:
            course = enrollment.course
            user_map = EdxUserMapping.objects.get(user_sis=enrollment.eleve.user)
            grades = service.client.get_grades(course.course_id, user_map.username_edx)
            enrollment.progression = min(max(float(grades.get("percent", 0)) * 100, 0), 100)
            enrollment.last_sync = timezone.now()
            enrollment.save()
        except Exception as e:
            logger.warning(f"Reconcile error for enrollment {enrollment.id}: {e}")


@shared_task
def reconcile_lms():
    """Réconciliation quotidienne LMS ↔ SIS, pour chaque établissement."""
    logger.info("Starting LMS reconciliation")
    for schema_name in _iter_tenant_schemas():
        with schema_context(schema_name):
            _reconcile_lms_for_current_schema()


def _sync_all_pending_eleves_for_current_schema():
    from apps.eleves.models import Eleve

    service = SyncService()
    pending = Eleve.objects.exclude(user__edx_mapping__isnull=False).select_related("user")[:200]
    count = 0
    for eleve in pending:
        try:
            service.sync_user_to_lms(eleve.user, role="student")
            count += 1
        except Exception as e:
            logger.error(f"Failed to sync eleve {eleve.id}: {e}")
    return count


@shared_task
def sync_all_pending_eleves():
    """Synchronise tous les élèves qui n'ont pas encore de mapping LMS."""
    total = 0
    for schema_name in _iter_tenant_schemas():
        with schema_context(schema_name):
            total += _sync_all_pending_eleves_for_current_schema()
    logger.info(f"Synced {total} eleves to LMS")
