import hashlib
import hmac
import json
from unittest.mock import Mock, patch

from django.test import TestCase, override_settings

from openedx.core.djangoapps.sis_grade_webhooks.tasks import (
    EVENT_TYPE,
    publish_assessment_grade,
)


@override_settings(
    SIS_GRADE_WEBHOOK_TARGETS=[
        {
            "url": "https://sis.example.test/api/v1/integration/webhook/lms/",
            "secret": "test-secret",
            "course_ids": ["course-v1:Org+Course+Run"],
        }
    ]
)
class PublishAssessmentGradeTest(TestCase):
    @patch("openedx.core.djangoapps.sis_grade_webhooks.tasks.requests.post")
    def test_publishes_signed_normalized_payload(self, post):
        post.return_value = Mock()
        payload = {
            "event_id": "event-1",
            "user": {"id": 1, "username": "learner"},
            "course": {"course_key": "course-v1:Org+Course+Run"},
            "subsection_id": "block-v1:Org+Course+Run+type@sequential+block@quiz",
            "score": 8,
            "max_score": 10,
            "timestamp": "2026-09-20T09:00:00+00:00",
        }

        publish_assessment_grade(payload)

        headers = post.call_args.kwargs["headers"]
        assert headers["X-Event-Type"] == EVENT_TYPE
        assert headers["X-Event-ID"] == "event-1"
        body = post.call_args.kwargs["data"]
        expected = hmac.new(b"test-secret", body, hashlib.sha256).hexdigest()
        assert headers["X-Signature"] == f"sha256={expected}"
        assert json.loads(body) == payload
        post.return_value.raise_for_status.assert_called_once_with()

    @patch("openedx.core.djangoapps.sis_grade_webhooks.tasks.requests.post")
    def test_ignores_target_for_another_course(self, post):
        publish_assessment_grade(
            {
                "event_id": "event-2",
                "course": {"course_key": "course-v1:Other+Course+Run"},
            }
        )

        post.assert_not_called()

    @override_settings(
        SIS_GRADE_WEBHOOK_TARGETS=[
            {"url": "https://sis.example.test/webhook/", "secret": ""}
        ]
    )
    @patch("openedx.core.djangoapps.sis_grade_webhooks.tasks.requests.post")
    def test_ignores_target_without_secret(self, post):
        publish_assessment_grade(
            {
                "event_id": "event-3",
                "course": {"course_key": "course-v1:Org+Course+Run"},
            }
        )

        post.assert_not_called()

    @override_settings(
        SIS_GRADE_WEBHOOK_TARGETS=[
            {"url": "http://invalid.example.test/webhook/", "secret": ""},
            {
                "url": "https://sis.example.test/webhook/",
                "secret": "valid-secret",
            },
        ]
    )
    @patch("openedx.core.djangoapps.sis_grade_webhooks.tasks.requests.post")
    def test_invalid_target_does_not_block_valid_target(self, post):
        post.return_value = Mock()

        publish_assessment_grade(
            {
                "event_id": "event-4",
                "course": {"course_key": "course-v1:Org+Course+Run"},
            }
        )

        post.assert_called_once()
