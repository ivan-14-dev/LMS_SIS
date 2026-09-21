"""Shared workflow audit and notification helpers."""

import logging

from django.apps import apps

logger = logging.getLogger("apps.workflow")


def _core_model(model_name):
    return apps.get_model("core", model_name)


def _object_identity(instance):
    meta = instance._meta
    return meta.app_label, meta.model_name, str(instance.pk), str(instance)


def record_workflow_event(
    request,
    instance,
    action,
    title,
    message="",
    recipients=None,
    metadata=None,
    notification_category=None,
):
    """Persist a workflow event and optional user notifications."""

    recipients = [recipient for recipient in (recipients or []) if recipient is not None]
    metadata = metadata or {}
    WorkflowEvent = _core_model("WorkflowEvent")
    WorkflowNotification = _core_model("WorkflowNotification")
    app_label, model_name, object_id, object_repr = _object_identity(instance)
    actor = getattr(request, "user", None)
    event = WorkflowEvent.objects.create(
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        tenant_id=getattr(getattr(request, "tenant", None), "id", None),
        request_id=getattr(request, "request_id", ""),
        app_label=app_label,
        model=model_name,
        object_id=object_id,
        object_repr=object_repr,
        action=action,
        title=title,
        message=message,
        metadata=metadata,
    )
    created_notifications = []
    for recipient in recipients:
        notification = WorkflowNotification.objects.create(
            recipient=recipient,
            event=event,
            category=notification_category or action,
            title=title,
            message=message or title,
            metadata=metadata,
        )
        created_notifications.append(notification)
    logger.info(
        "Workflow event",
        extra={
            "tenant_id": event.tenant_id,
            "request_id": event.request_id,
            "app_label": event.app_label,
            "model": event.model,
            "object_id": event.object_id,
            "action": action,
            "actor_id": event.actor_id,
        },
    )
    return event, created_notifications


def workflow_history_queryset(instance):
    """Return workflow history queryset for the given object."""

    WorkflowEvent = _core_model("WorkflowEvent")
    app_label, model_name, object_id, _ = _object_identity(instance)
    return WorkflowEvent.objects.filter(
        app_label=app_label,
        model=model_name,
        object_id=object_id,
    ).select_related("actor").order_by("-created_at")
