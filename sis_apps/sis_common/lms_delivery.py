"""Durable provisioning requests; remote ownership makes replay idempotent."""

import requests


def begin_delivery(service, event_type, aggregate_type, aggregate_id, payload):
    if not service.enqueue_failures:
        return None
    from apps.integration.models import OutboxEvent
    from django.utils import timezone

    return OutboxEvent.objects.create(
        event_type=event_type,
        aggregate_type=aggregate_type,
        aggregate_id=str(aggregate_id),
        payload=payload,
        statut="processing",
        derniere_tentative=timezone.now(),
    )


def finish_delivery(event, error=None):
    if event is None:
        return
    from sis_common.lms_access_sync import permanent_access_failure, save_claimed_outbox_event

    event.statut = "done"
    event.erreur = ""
    if error is not None:
        event.statut = "dead" if permanent_access_failure(error) else "pending"
        event.erreur = str(error)
        event.nb_tentatives = min(event.nb_tentatives + 1, 32767)
    save_claimed_outbox_event(event)


def transient_delivery_failure(error):
    from django.core.exceptions import ImproperlyConfigured

    if isinstance(error, (ImproperlyConfigured, requests.ConnectionError, requests.Timeout)):
        return True
    response = getattr(error, "response", None)
    return (
        isinstance(error, requests.HTTPError)
        and response is not None
        and (response.status_code >= 500 or response.status_code in (408, 429))
    )


def recover_interrupted_provisioning():
    from datetime import timedelta

    from apps.integration.models import OutboxEvent
    from django.db import transaction
    from django.utils import timezone

    with transaction.atomic():
        ids = list(
            OutboxEvent.objects.select_for_update(skip_locked=True)
            .filter(
                event_type__in=("user.sync", "course.create", "enrollment.create"),
                statut="processing",
                derniere_tentative__lt=timezone.now() - timedelta(minutes=10),
            )
            .order_by("derniere_tentative")
            .values_list("pk", flat=True)[:100]
        )
        return OutboxEvent.objects.filter(pk__in=ids).update(
            statut="pending",
            erreur="Reprise du même provisioning après interruption du traitement.",
            updated_at=timezone.now(),
        )
