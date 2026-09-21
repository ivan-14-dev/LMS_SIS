"""Shared delivery helpers for workflow notifications."""

from copy import deepcopy

import requests
from django.apps import apps
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from django_tenants.utils import schema_context

DELIVERY_CHANNELS = ("in_app", "email", "sms", "webhook")


def _core_model(model_name):
    return apps.get_model("core", model_name)


def _now_iso():
    return timezone.now().isoformat()


def _channel_enabled(recipient, channel, category):
    preferences = getattr(recipient, "preferences_notification", {}) or {}
    if preferences.get(channel) is False:
        return False
    channels = preferences.get("channels", {})
    if isinstance(channels, dict) and channels.get(channel) is False:
        return False
    categories = preferences.get("categories", {})
    category_settings = categories.get(category, {}) if isinstance(categories, dict) else {}
    if category_settings is False:
        return False
    if isinstance(category_settings, dict) and category_settings.get(channel) is False:
        return False
    return True


def _delivery_map(metadata):
    metadata = deepcopy(metadata or {})
    delivery = metadata.get("delivery")
    if not isinstance(delivery, dict):
        delivery = {}
        metadata["delivery"] = delivery
    return metadata, delivery


def _aggregate_status(targets):
    statuses = {target.get("status") for target in (targets or [])}
    if "failed" in statuses:
        return "failed"
    if "retrying" in statuses:
        return "retrying"
    if "queued" in statuses:
        return "queued"
    if "sent" in statuses:
        return "sent"
    if "skipped" in statuses:
        return "skipped"
    return "pending"


def delivery_channels(metadata):
    delivery = (metadata or {}).get("delivery", {})
    if not isinstance(delivery, dict):
        return []
    return [channel for channel in DELIVERY_CHANNELS if channel in delivery]


def delivery_status_summary(metadata):
    delivery = (metadata or {}).get("delivery", {})
    if not isinstance(delivery, dict):
        return []
    summary = []
    for channel in DELIVERY_CHANNELS:
        status = (delivery.get(channel) or {}).get("status")
        if status:
            summary.append(f"{channel}:{status}")
    return summary


def delivery_last_errors(metadata):
    delivery = (metadata or {}).get("delivery", {})
    if not isinstance(delivery, dict):
        return []
    errors = []
    for channel in DELIVERY_CHANNELS:
        error = (delivery.get(channel) or {}).get("last_error")
        if error:
            errors.append(f"{channel}:{error}")
    return errors


def notification_matches_delivery_filters(notification, channel="", status=""):
    delivery = (getattr(notification, "metadata", {}) or {}).get("delivery", {})
    if not isinstance(delivery, dict):
        return not channel and not status
    if channel:
        details = delivery.get(channel, {})
        if not details:
            return False
        if status and details.get("status") != status:
            return False
        return True
    if status:
        return any((details or {}).get("status") == status for details in delivery.values())
    return True


def summarize_notification_deliveries(notifications):
    summary = {
        "total_notifications": 0,
        "by_category": {},
        "by_channel": {},
        "by_status": {},
        "by_channel_status": {},
    }
    for notification in notifications:
        summary["total_notifications"] += 1
        category = getattr(notification, "category", "") or "uncategorized"
        summary["by_category"][category] = summary["by_category"].get(category, 0) + 1
        delivery = (getattr(notification, "metadata", {}) or {}).get("delivery", {})
        if not isinstance(delivery, dict):
            continue
        for channel, details in delivery.items():
            status = (details or {}).get("status", "pending")
            summary["by_channel"][channel] = summary["by_channel"].get(channel, 0) + 1
            summary["by_status"][status] = summary["by_status"].get(status, 0) + 1
            channel_status_key = f"{channel}:{status}"
            summary["by_channel_status"][channel_status_key] = (
                summary["by_channel_status"].get(channel_status_key, 0) + 1
            )
    return summary


def _update_notification_channel(notification, channel, status, attempts=None, error="", detail="", extra=None):
    metadata, delivery = _delivery_map(notification.metadata)
    existing = delivery.get(channel, {})
    payload = {
        **existing,
        "status": status,
        "updated_at": _now_iso(),
    }
    if attempts is not None:
        payload["attempts"] = attempts
    if error:
        payload["last_error"] = error
    elif "last_error" in payload:
        payload.pop("last_error")
    if detail:
        payload["detail"] = detail
    elif "detail" in payload:
        payload.pop("detail")
    if extra:
        payload.update(extra)
    delivery[channel] = payload
    notification.metadata = metadata
    notification.save(update_fields=["metadata"])
    return payload


def initialize_notification_delivery(created_notifications, channels, sms_gateway_url="", webhook_urls=None):
    channels = channels or []
    webhook_urls = webhook_urls or []
    for notification in created_notifications:
        _update_notification_channel(notification, "in_app", "sent", attempts=1)
        if "email" in channels:
            _update_notification_channel(notification, "email", "queued", attempts=0)
        if "sms" in channels:
            if sms_gateway_url:
                _update_notification_channel(notification, "sms", "queued", attempts=0)
            else:
                _update_notification_channel(
                    notification,
                    "sms",
                    "skipped",
                    attempts=0,
                    detail="Passerelle SMS non configurée.",
                )
        if "webhook" in channels:
            if webhook_urls:
                _update_notification_channel(notification, "webhook", "queued", attempts=0)
            else:
                _update_notification_channel(
                    notification,
                    "webhook",
                    "skipped",
                    attempts=0,
                    detail="Aucune URL webhook configurée.",
                )


def initialize_event_delivery(event, channels, webhook_urls=None):
    channels = channels or []
    webhook_urls = webhook_urls or []
    metadata, delivery = _delivery_map(event.metadata)
    if "webhook" in channels:
        if webhook_urls:
            delivery["webhook"] = {
                "status": "queued",
                "updated_at": _now_iso(),
                "targets": [{"url": url, "status": "queued", "attempts": 0} for url in webhook_urls],
            }
        else:
            delivery["webhook"] = {
                "status": "skipped",
                "updated_at": _now_iso(),
                "detail": "Aucune URL webhook configurée.",
                "targets": [],
            }
    event.metadata = metadata
    event.save(update_fields=["metadata"])


def update_notification_channel_status(schema_name, notification_id, channel, status, attempts=None, error="", detail=""):
    with schema_context(schema_name):
        WorkflowNotification = _core_model("WorkflowNotification")
        notification = WorkflowNotification.objects.get(pk=notification_id)
        return _update_notification_channel(
            notification,
            channel,
            status,
            attempts=attempts,
            error=error,
            detail=detail,
        )


def update_event_webhook_status(schema_name, event_id, webhook_url, status, attempts=None, error=""):
    with schema_context(schema_name):
        WorkflowEvent = _core_model("WorkflowEvent")
        WorkflowNotification = _core_model("WorkflowNotification")
        event = WorkflowEvent.objects.get(pk=event_id)
        metadata, delivery = _delivery_map(event.metadata)
        webhook_delivery = delivery.get("webhook", {})
        targets = webhook_delivery.get("targets", [])
        updated = False
        for target in targets:
            if target.get("url") == webhook_url:
                target["status"] = status
                target["updated_at"] = _now_iso()
                if attempts is not None:
                    target["attempts"] = attempts
                if error:
                    target["last_error"] = error
                elif "last_error" in target:
                    target.pop("last_error")
                updated = True
                break
        if not updated:
            target = {"url": webhook_url, "status": status, "updated_at": _now_iso()}
            if attempts is not None:
                target["attempts"] = attempts
            if error:
                target["last_error"] = error
            targets.append(target)
        webhook_delivery["targets"] = targets
        webhook_delivery["status"] = _aggregate_status(targets)
        webhook_delivery["updated_at"] = _now_iso()
        delivery["webhook"] = webhook_delivery
        event.metadata = metadata
        event.save(update_fields=["metadata"])
        for notification in WorkflowNotification.objects.filter(event=event):
            _update_notification_channel(
                notification,
                "webhook",
                webhook_delivery["status"],
                attempts=attempts,
                error=error,
            )
        return webhook_delivery


def send_notification_email(schema_name, notification_id):
    with schema_context(schema_name):
        WorkflowNotification = _core_model("WorkflowNotification")
        notification = WorkflowNotification.objects.select_related("recipient", "event").get(pk=notification_id)
        recipient = notification.recipient
        if not recipient.email:
            _update_notification_channel(notification, "email", "skipped", detail="Aucune adresse email.")
            return {"status": "skipped"}
        if not _channel_enabled(recipient, "email", notification.category):
            _update_notification_channel(notification, "email", "skipped", detail="Canal email désactivé par l'utilisateur.")
            return {"status": "skipped"}
        send_mail(
            notification.title,
            notification.message,
            getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@example.com"),
            [recipient.email],
            fail_silently=False,
        )
        _update_notification_channel(notification, "email", "sent", detail=recipient.email)
        return {"status": "sent"}


def send_notification_sms(schema_name, notification_id, gateway_url):
    if not gateway_url:
        update_notification_channel_status(
            schema_name,
            notification_id,
            "sms",
            "skipped",
            detail="Passerelle SMS non configurée.",
        )
        return {"status": "skipped"}
    with schema_context(schema_name):
        WorkflowNotification = _core_model("WorkflowNotification")
        notification = WorkflowNotification.objects.select_related("recipient", "event").get(pk=notification_id)
        recipient = notification.recipient
        if not getattr(recipient, "telephone", ""):
            _update_notification_channel(notification, "sms", "skipped", detail="Aucun numéro de téléphone.")
            return {"status": "skipped"}
        if not _channel_enabled(recipient, "sms", notification.category):
            _update_notification_channel(notification, "sms", "skipped", detail="Canal SMS désactivé par l'utilisateur.")
            return {"status": "skipped"}
        payload = {
            "notification_id": notification.id,
            "category": notification.category,
            "recipient": {
                "id": recipient.id,
                "phone": recipient.telephone,
                "email": getattr(recipient, "email", ""),
                "username": getattr(recipient, "username", ""),
            },
            "title": notification.title,
            "message": notification.message,
            "metadata": notification.metadata,
        }
        response = requests.post(gateway_url, json=payload, timeout=10)
        response.raise_for_status()
        _update_notification_channel(notification, "sms", "sent", detail=recipient.telephone)
        return {"status": "sent"}


def send_notification_webhook(schema_name, event_id, webhook_url):
    if not webhook_url:
        return {"status": "skipped"}
    with schema_context(schema_name):
        WorkflowEvent = _core_model("WorkflowEvent")
        event = WorkflowEvent.objects.prefetch_related("notifications").get(pk=event_id)
        payload = {
            "event_id": event.id,
            "action": event.action,
            "title": event.title,
            "message": event.message,
            "app_label": event.app_label,
            "model": event.model,
            "object_id": event.object_id,
            "object_repr": event.object_repr,
            "metadata": event.metadata,
            "notifications": [
                {
                    "id": notification.id,
                    "recipient_id": notification.recipient_id,
                    "category": notification.category,
                    "title": notification.title,
                    "message": notification.message,
                    "metadata": notification.metadata,
                }
                for notification in event.notifications.all()
            ],
        }
        response = requests.post(webhook_url, json=payload, timeout=10)
        response.raise_for_status()
    update_event_webhook_status(schema_name, event_id, webhook_url, "sent")
    return {"status": "sent"}
