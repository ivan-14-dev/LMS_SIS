import uuid
from datetime import timedelta

from apps.integration.webhook_handlers import WebhookHandler
from django.apps import apps
from django.utils import timezone

from sis_common.tests.test_grade_entry import GradeEntryFixture


class LMSGradeProtectionTests(GradeEntryFixture):
    def setUp(self):
        super().setUp()
        self.grade_logs = apps.get_model("integration.EdxGradeLog")
        course_values = {
            "matiere": self.subject,
            "classe": self.classe,
        } if self.secondary else {"ecue": self.subject}
        self.course = apps.get_model("integration.EdxCourseMapping").objects.create(
            **course_values, course_id="course-v1:TEST+grades+2026", course_name="Notes"
        )
        self.mapping = apps.get_model("integration.EdxUserMapping").objects.create(
            user_sis=self.learners[0].user, username_edx="grade-learner"
        )
        learner_field = "eleve" if self.secondary else "etudiant"
        self.enrollment = apps.get_model("integration.EdxEnrollment").objects.create(
            course=self.course, **{learner_field: self.learners[0]}
        )
        apps.get_model("integration.EdxAssessmentMapping").objects.create(
            course=self.course, evaluation=self.evaluation, subsection_id="block-v1:TEST+grades+2026+type@sequential"
        )
        self.handler = WebhookHandler(
            apps.get_model("integration.EdxUserMapping"),
            apps.get_model("integration.EdxCourseMapping"),
            apps.get_model("integration.EdxEnrollment"),
            self.grade_logs,
            type(self.learners[0]),
            self.note_model,
        )

    def deliver(self, score="12"):
        event_id = uuid.uuid4().hex
        payload = {
            "_event_id": event_id,
            "user": {"username": self.mapping.username_edx},
            "course": {"course_key": self.course.course_id},
            "subsection_id": "block-v1:TEST+grades+2026+type@sequential",
            "score": score,
            "max_score": "20",
            "timestamp": (timezone.now() + timedelta(seconds=1)).isoformat(),
        }
        assert self.handler.handle_grade_updated(payload) is True
        return self.grade_logs.objects.get(event_id=event_id)

    def test_staff_correction_is_not_overwritten_by_new_lms_event(self):
        first = self.deliver()
        assert first.imported_to_sis is True
        assert self.evaluation.notes.get().valeur == 12
        updated = self.deliver("15")
        assert updated.imported_to_sis is True
        assert self.evaluation.notes.get().valeur == 15

        self.client.force_authenticate(self.teacher)
        changed = self.save_grades([self.row(self.learners[0], "18")])
        assert changed.status_code == 200, changed.data
        note = self.evaluation.notes.get()
        assert note.valeur == 18
        retained = self.deliver("4")
        note.refresh_from_db()
        assert note.valeur == 18
        assert retained.imported_to_sis is False
        assert retained.note_sis_id is None

    def test_existing_staff_note_and_closed_period_retain_lms_evidence_only(self):
        self.note_model.objects.create(
            evaluation=self.evaluation,
            **{self.learner_field: self.learners[0].pk},
            valeur=17,
            statut="presente",
            saisi_par=self.author,
        )
        staff_event = self.deliver("8")
        assert staff_event.imported_to_sis is False
        assert self.evaluation.notes.get().valeur == 17

        field = "cloturee" if self.secondary else "cloture"
        setattr(self.period, field, True)
        self.period.save(update_fields=[field])
        closed_event = self.deliver("2")
        assert closed_event.imported_to_sis is False
        assert self.evaluation.notes.get().valeur == 17
        self.evaluation.notes.all().delete()
        assert self.deliver("5").imported_to_sis is False
        assert not self.evaluation.notes.exists()

    def test_inactive_enrollment_or_mapping_cannot_import_a_note(self):
        self.enrollment.is_active = False
        self.enrollment.save(update_fields=["is_active"])
        assert self.deliver().imported_to_sis is False
        self.enrollment.is_active = True
        self.enrollment.save(update_fields=["is_active"])
        self.mapping.actif = False
        self.mapping.save(update_fields=["actif"])
        assert self.deliver().imported_to_sis is False
        self.mapping.actif = True
        self.mapping.save(update_fields=["actif"])
        self.course.actif = False
        self.course.save(update_fields=["actif"])
        assert self.deliver().imported_to_sis is False
        assert not self.evaluation.notes.exists()
        assert self.grade_logs.objects.count() == 3
