"""Shared delivery helpers for workflow notifications."""

from django.apps import apps
from django.conf import settings
from django.core.mail import send_mail
from django_tenants.utils import schema_context
import requests


def _core_model(model_name):
    return apps.get_model("core", model_name)


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


def send_notification_email(schema_name, notification_id):
    with schema_context(schema_name):
        WorkflowNotification = _core_model("WorkflowNotification")
        notification = WorkflowNotification.objects.select_related("recipient", "event").get(pk=notification_id)
        recipient = notification.recipient
        if not recipient.email or not _channel_enabled(recipient, "email", notification.category):
            return False
        send_mail(
            notification.title,
            notification.message,
            getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@example.com"),
            [recipient.email],
            fail_silently=False,
        )
        return True


def send_notification_sms(schema_name, notification_id, gateway_url):
    if not gateway_url:
        return False
    with schema_context(schema_name):
        WorkflowNotification = _core_model("WorkflowNotification")
        notification = WorkflowNotification.objects.select_related("recipient", "event").get(pk=notification_id)
        recipient = notification.recipient
        if not getattr(recipient, "telephone", "") or not _channel_enabled(recipient, "sms", notification.category):
            return False
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
        return True


def send_notification_webhook(schema_name, event_id, webhook_url):
    if not webhook_url:
        return False
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
        return True
