"""System-level integration checks for the SIS Secondaire service."""

import hashlib
import hmac
import json
from pathlib import Path
from unittest.mock import patch

from django.apps import apps
from django.conf import settings
from django.test import override_settings
from django.urls import resolve
from rest_framework.test import APIRequestFactory


def test_project_models_have_versioned_initial_migrations():
    """All local applications with models provide an initial migration."""
    apps_root = Path(settings.BASE_DIR) / "apps"
    project_apps = [
        app_config
        for app_config in apps.get_app_configs()
        if list(app_config.get_models()) and apps_root in Path(app_config.path).parents
    ]

    missing = [
        app_config.label
        for app_config in project_apps
        if not (Path(app_config.path) / "migrations" / "0001_initial.py").exists()
    ]

    assert missing == []


def test_public_and_authenticated_routes_resolve():
    """Health and protected integration routes are registered."""
    assert resolve("/health/").url_name == "health-check"
    assert resolve("/api/v1/integration/sync/status/").url_name == "sync-status"


def test_signed_lms_webhook_queues_user_sync():
    """A valid LMS webhook is authenticated and passed to Celery."""
    from apps.integration.api import webhook_lms

    payload = {"user": {"id": 1, "username": "pupil"}}
    body = json.dumps(payload).encode()
    signature = hmac.new(
        settings.WEBHOOK_SECRET.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()
    request = APIRequestFactory().post(
        "/api/v1/integration/webhook/lms/",
        data=body,
        content_type="application/json",
        HTTP_X_SIGNATURE=f"sha256={signature}",
        HTTP_X_EVENT_TYPE="user.created",
    )

    local_cache = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        },
    }
    with override_settings(CACHES=local_cache):
        with patch("apps.integration.tasks.process_user_webhook.delay") as delay:
            response = webhook_lms(request)

    assert response.status_code == 200
    event_type, queued_payload = delay.call_args.args
    assert event_type == "user.created"
    assert queued_payload["user"] == payload["user"]
    assert queued_payload["_event_id"]
