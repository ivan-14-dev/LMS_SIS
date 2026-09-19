"""Celery app for SIS Secondaire."""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("sis_secondaire")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
