"""Tenant-scoped monitoring and dispatch; replay remains owned by the publisher."""

import logging

from django_tenants.utils import get_public_schema_name, get_tenant_model, schema_context
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from sis_common.lms_tenants import current_lms_tenant

logger = logging.getLogger(__name__)


def outbox_queryset(request):
    from apps.integration.models import OutboxEvent

    current_lms_tenant(request)
    statuses = request.query_params.getlist("statut")
    if any(value not in dict(OutboxEvent.STATUT_CHOICES) for value in statuses):
        raise ValidationError({"statut": "Statut invalide."})
    queryset = OutboxEvent.objects.order_by("-created_at", "-pk")
    return queryset.filter(statut__in=statuses) if statuses else queryset


def request_outbox_processing(request):
    from apps.integration.tasks import publish_tenant_outbox_events

    tenant = current_lms_tenant(request)
    if not isinstance(request.data, dict) or request.data or request.query_params:
        raise ValidationError({"error": "Envoyez uniquement un objet JSON vide, sans paramètres."})
    try:
        task = publish_tenant_outbox_events.delay(tenant.pk, tenant.schema_name)
    except Exception:
        logger.exception("Outbox dispatch not confirmed actor_id=%s tenant_id=%s", request.user.pk, tenant.pk)
        return Response(
            {"error": "La mise en file n'est pas confirmée. Les événements sont conservés ; réessayez plus tard."},
            status=503,
        )
    logger.info(
        "Outbox processing queued actor_id=%s tenant_id=%s task_id=%s", request.user.pk, tenant.pk, task.id
    )
    return Response({"status": "queued", "task_id": task.id}, status=202)


def publish_tenant_outbox(tenant_id, schema_name, publisher):
    if (
        type(tenant_id) is not int
        or not isinstance(schema_name, str)
        or not schema_name
        or schema_name == get_public_schema_name()
        or not get_tenant_model().objects.filter(pk=tenant_id, schema_name=schema_name).exists()
    ):
        logger.error("Refusing outbox processing for an invalid tenant")
        raise ValueError("Établissement de traitement invalide.")
    with schema_context(schema_name):
        return publisher()
