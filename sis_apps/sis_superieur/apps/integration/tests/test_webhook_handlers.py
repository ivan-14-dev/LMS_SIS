from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock, Mock

from apps.integration.webhook_handlers import WebhookHandler


class WebhookHandlerContractTestCase(TestCase):
    def setUp(self):
        self.user_mappings = MagicMock()
        self.enrollments = MagicMock()
        self.handler = WebhookHandler(
            self.user_mappings,
            MagicMock(),
            self.enrollments,
            MagicMock(),
            MagicMock(),
            MagicMock(),
        )

    def test_public_course_grade_event_updates_progression(self):
        learner = SimpleNamespace(etudiant_profile=object())
        self.user_mappings.objects.get.return_value = SimpleNamespace(user_sis=learner)
        enrollment = MagicMock()
        self.enrollments.objects.get.return_value = enrollment
        payload = {
            "data": {
                "grade": {
                    "user_id": 42,
                    "course": {"course_key": "course-v1:Org+Course+Run"},
                    "percent_grade": 0.75,
                }
            }
        }

        handled = self.handler.handle(
            "org.openedx.learning.course.persistent_grade_summary.changed.v1",
            payload,
        )

        assert handled
        assert enrollment.progression == 75
        enrollment.save.assert_called_once_with(
            update_fields=["progression", "last_sync"]
        )

    def test_handler_failure_is_propagated(self):
        self.handler.handle_grade_updated = Mock(return_value=False)

        assert not self.handler.handle("grade.updated", {})
