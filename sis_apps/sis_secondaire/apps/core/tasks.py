"""Celery tasks for core."""

from celery import shared_task

from sis_common.notification_channels import (
    send_notification_email,
    send_notification_sms,
    send_notification_webhook,
)


@shared_task(autoretry_for=(Exception,), retry_backoff=True, max_retries=5)
def dispatch_notification_email(notification_id, schema_name):
    return send_notification_email(schema_name, notification_id)


@shared_task(autoretry_for=(Exception,), retry_backoff=True, max_retries=5)
def dispatch_notification_sms(notification_id, schema_name, gateway_url):
    return send_notification_sms(schema_name, notification_id, gateway_url)


@shared_task(autoretry_for=(Exception,), retry_backoff=True, max_retries=5)
def dispatch_notification_webhook(event_id, schema_name, webhook_url):
    return send_notification_webhook(schema_name, event_id, webhook_url)
