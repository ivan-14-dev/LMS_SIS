"""Celery tasks for core."""

from celery import shared_task

from sis_common.notification_channels import (
    send_notification_email,
    send_notification_sms,
    send_notification_webhook,
    update_event_webhook_status,
    update_notification_channel_status,
)


@shared_task(bind=True, retry_backoff=True, max_retries=5)
def dispatch_notification_email(self, notification_id, schema_name):
    attempts = self.request.retries + 1
    try:
        result = send_notification_email(schema_name, notification_id)
        if result.get("status") == "sent":
            update_notification_channel_status(schema_name, notification_id, "email", "sent", attempts=attempts)
        return result
    except Exception as exc:
        status = "failed" if self.request.retries >= self.max_retries else "retrying"
        update_notification_channel_status(schema_name, notification_id, "email", status, attempts=attempts, error=str(exc))
        if status == "retrying":
            raise self.retry(exc=exc)
        raise


@shared_task(bind=True, retry_backoff=True, max_retries=5)
def dispatch_notification_sms(self, notification_id, schema_name, gateway_url):
    attempts = self.request.retries + 1
    try:
        result = send_notification_sms(schema_name, notification_id, gateway_url)
        if result.get("status") == "sent":
            update_notification_channel_status(schema_name, notification_id, "sms", "sent", attempts=attempts)
        return result
    except Exception as exc:
        status = "failed" if self.request.retries >= self.max_retries else "retrying"
        update_notification_channel_status(schema_name, notification_id, "sms", status, attempts=attempts, error=str(exc))
        if status == "retrying":
            raise self.retry(exc=exc)
        raise


@shared_task(bind=True, retry_backoff=True, max_retries=5)
def dispatch_notification_webhook(self, event_id, schema_name, webhook_url):
    attempts = self.request.retries + 1
    try:
        result = send_notification_webhook(schema_name, event_id, webhook_url)
        if result.get("status") == "sent":
            update_event_webhook_status(schema_name, event_id, webhook_url, "sent", attempts=attempts)
        return result
    except Exception as exc:
        status = "failed" if self.request.retries >= self.max_retries else "retrying"
        update_event_webhook_status(schema_name, event_id, webhook_url, status, attempts=attempts, error=str(exc))
        if status == "retrying":
            raise self.retry(exc=exc)
        raise
