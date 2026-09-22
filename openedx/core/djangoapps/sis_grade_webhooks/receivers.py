"""Signal receivers that queue assessment grade change events for SIS webhooks."""
from uuid import uuid4

from django.dispatch import receiver
from django.utils import timezone

from openedx.core.djangoapps.signals.signals import COURSE_ASSESSMENT_GRADE_CHANGED

from .tasks import publish_assessment_grade


@receiver(
    COURSE_ASSESSMENT_GRADE_CHANGED,
    dispatch_uid="sis_publish_assessment_grade",
)
def queue_assessment_grade(
    sender,
    user,
    course_id,
    subsection_id,
    subsection_grade,
    subsection_max_grade=None,
    **kwargs,
):
    """Queue the detailed assessment grade without delaying learner requests."""
    del sender, kwargs
    max_grade = (
        float(subsection_max_grade) if subsection_max_grade is not None else 100.0
    )
    if max_grade <= 0:
        return
    publish_assessment_grade.delay(
        {
            "event_id": uuid4().hex,
            "user": {"id": user.id, "username": user.username},
            "course": {"course_key": str(course_id)},
            "subsection_id": str(subsection_id),
            "score": float(subsection_grade),
            "max_score": max_grade,
            "timestamp": timezone.now().isoformat(),
        }
    )
