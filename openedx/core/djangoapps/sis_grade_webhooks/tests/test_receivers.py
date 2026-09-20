from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from openedx.core.djangoapps.sis_grade_webhooks.receivers import queue_assessment_grade


class QueueAssessmentGradeTest(SimpleTestCase):
    @patch(
        "openedx.core.djangoapps.sis_grade_webhooks.receivers."
        "publish_assessment_grade.delay"
    )
    def test_queues_complete_grade_payload(self, delay):
        user = Mock(pk=42, username="learner")

        queue_assessment_grade(
            sender=None,
            user=user,
            course_id="course-v1:Org+Course+Run",
            subsection_id="block-v1:Org+Course+Run+type@sequential+block@quiz",
            subsection_grade=8,
            subsection_max_grade=10,
        )

        payload = delay.call_args.args[0]
        self.assertEqual(payload["user"], {"id": 42, "username": "learner"})
        self.assertEqual(payload["score"], 8.0)
        self.assertEqual(payload["max_score"], 10.0)
        self.assertEqual(len(payload["event_id"]), 64)

    @patch(
        "openedx.core.djangoapps.sis_grade_webhooks.receivers."
        "publish_assessment_grade.delay"
    )
    def test_ignores_zero_max_grade(self, delay):
        queue_assessment_grade(
            sender=None,
            user=Mock(pk=42, username="learner"),
            course_id="course-v1:Org+Course+Run",
            subsection_id="subsection",
            subsection_grade=0,
            subsection_max_grade=0,
        )

        delay.assert_not_called()
