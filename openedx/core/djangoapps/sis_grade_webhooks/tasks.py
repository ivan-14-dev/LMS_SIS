import hashlib
import hmac
import json
from urllib.parse import urlsplit

import requests
from celery import shared_task
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

EVENT_TYPE = "org.openedx.learning.course.assessment.grade.changed.v1"


def _eligible_targets(course_id):
    targets = getattr(settings, "SIS_GRADE_WEBHOOK_TARGETS", [])
    if not isinstance(targets, (list, tuple)):
        raise ImproperlyConfigured("SIS_GRADE_WEBHOOK_TARGETS must be a list.")
    for target in targets:
        if not isinstance(target, dict):
            raise ImproperlyConfigured(
                "Each SIS grade webhook target must be a mapping."
            )
        configured_courses = target.get("course_ids", [])
        if not configured_courses or course_id in configured_courses:
            yield target


def _validate_target(target):
    url = target.get("url", "")
    secret = target.get("secret", "")
    parsed = urlsplit(url)
    if (
        not secret
        or not parsed.netloc
        or parsed.scheme not in ({"http", "https"} if settings.DEBUG else {"https"})
    ):
        raise ImproperlyConfigured("Invalid SIS grade webhook target configuration.")
    if parsed.username or parsed.password or parsed.fragment:
        raise ImproperlyConfigured(
            "SIS webhook URLs cannot contain credentials or fragments."
        )
    return url, secret


@shared_task(
    autoretry_for=(requests.RequestException,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=5,
)
def publish_assessment_grade(payload):
    """Publish one normalized assessment grade to its configured SIS targets."""
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    for target in _eligible_targets(payload["course"]["course_key"]):
        url, secret = _validate_target(target)
        signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        response = requests.post(
            url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "X-Event-Type": EVENT_TYPE,
                "X-Event-ID": payload["event_id"],
                "X-Signature": f"sha256={signature}",
            },
            timeout=10,
        )
        response.raise_for_status()
