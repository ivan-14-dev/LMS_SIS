"""Configuration Celery Beat - SIS Secondaire."""

from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    "publish-outbox-every-minute": {
        "task": "apps.integration.tasks.publish_outbox_events",
        "schedule": 60.0,
    },
    "reconcile-lms-daily": {
        "task": "apps.integration.tasks.reconcile_lms",
        "schedule": crontab(hour=2, minute=0),
    },
    "sync-pending-eleves-daily": {
        "task": "apps.integration.tasks.sync_all_pending_eleves",
        "schedule": crontab(hour=3, minute=0),
    },
}
