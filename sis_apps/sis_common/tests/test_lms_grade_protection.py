import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

from apps.integration.webhook_handlers import WebhookHandler
from django.apps import apps
from django.contrib.auth.models import Permission
from django.db import connection, connections
from django.test import TransactionTestCase
from django.utils import timezone
from django_tenants.utils import schema_context
from rest_framework.test import APIClient

from sis_common.tests.test_grade_entry import GradeEntryFixture


class LMSGradeFixture(GradeEntryFixture):
    def setUp(self):
        super().setUp()
        self.grade_logs = apps.get_model("integration.EdxGradeLog")
        course_values = (
            {
                "matiere": self.subject,
                "classe": self.classe,
            }
            if self.secondary
            else {"ecue": self.subject}
        )
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
        self.assessment = apps.get_model("integration.EdxAssessmentMapping").objects.create(
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

    def deliver(self, score="12", **extra):
        event_id = uuid.uuid4().hex
        payload = {
            "_event_id": event_id,
            "user": {"username": self.mapping.username_edx},
            "course": {"course_key": self.course.course_id},
            "subsection_id": "block-v1:TEST+grades+2026+type@sequential",
            "score": score,
            "max_score": "20",
            "timestamp": (timezone.now() + timedelta(seconds=1)).isoformat(),
            **extra,
        }
        assert self.handler.handle_grade_updated(payload) is True
        return self.grade_logs.objects.get(event_id=payload["_event_id"])

    def review(self, proposal, decision="approve", **extra):
        return self.client.post(
            f"{self.url}examiner_proposition_lms/",
            {"proposal_id": proposal.pk, "decision": decision, **extra},
            format="json",
        )


class LMSGradeProtectionTests(LMSGradeFixture):
    def test_enveloped_grade_is_only_staged_once_as_a_proposal(self):
        event_id = uuid.uuid4().hex
        payload = {
            "_event_id": event_id,
            "data": {
                "user": {"username": self.mapping.username_edx},
                "course": {"course_key": self.course.course_id},
                "subsection_id": self.assessment.subsection_id,
                "score": "12",
                "max_score": "20",
                "timestamp": timezone.now().isoformat(),
            },
        }
        assert self.handler.handle_grade_updated(payload) is True
        assert self.handler.handle_grade_updated(payload) is True
        proposal = self.grade_logs.objects.get(event_id=event_id)
        assert proposal.review_status == "pending"
        assert proposal.imported_to_sis is False
        assert not self.evaluation.notes.exists()

    def test_staff_correction_is_not_overwritten_by_new_lms_event(self):
        first = self.deliver()
        assert first.imported_to_sis is False
        assert first.review_status == "pending"
        assert not self.evaluation.notes.exists()
        self.client.force_authenticate(self.teacher)
        accepted = self.review(first)
        assert accepted.status_code == 200, accepted.data
        first.refresh_from_db()
        assert first.reviewed_by_id == self.teacher.pk
        assert first.reviewed_at is not None
        assert first.imported_to_sis is True
        assert self.evaluation.notes.get().valeur == 12
        updated = self.deliver("15")
        assert updated.imported_to_sis is False
        assert self.review(updated).status_code == 409
        assert self.evaluation.notes.get().valeur == 12

        changed = self.save_grades([self.row(self.learners[0], "18")])
        assert changed.status_code == 200, changed.data
        note = self.evaluation.notes.get()
        assert note.valeur == 18
        retained = self.deliver("4")
        note.refresh_from_db()
        assert note.valeur == 18
        assert retained.imported_to_sis is False
        assert retained.note_sis_id is None

    def test_receipt_replay_and_rejection_never_publish_or_change_averages(self):
        proposal = self.deliver()
        replay = self.deliver(_event_id=proposal.event_id)
        assert replay.pk == proposal.pk
        assert self.grade_logs.objects.count() == 1
        assert not self.evaluation.notes.exists()
        statistics = self.client.get(f"{self.url}statistiques/")
        assert statistics.status_code == 200
        assert statistics.data["moyenne"] is None
        assert self.review(proposal, "reject").status_code == 400
        rejected = self.review(proposal, "reject", reason="Copie à revoir")
        assert rejected.status_code == 200, rejected.data
        proposal.refresh_from_db()
        assert proposal.review_status == "rejected"
        assert proposal.review_reason == "Copie à revoir"
        assert not self.evaluation.notes.exists()
        assert self.review(proposal).status_code == 409

    def test_only_latest_proposal_can_be_approved_once_with_audit(self):
        older = self.deliver("10", timestamp=(timezone.now() - timedelta(minutes=1)).isoformat())
        newer = self.deliver("16")
        assert self.review(older).status_code == 409
        accepted = self.review(newer)
        assert accepted.status_code == 200, accepted.data
        assert self.review(newer).status_code == 409
        assert self.evaluation.notes.count() == 1
        assert self.evaluation.notes.get().valeur == 16
        audit = apps.get_model("core.WorkflowEvent").objects.get(action="lms_grade_review")
        assert audit.actor_id == self.admin.pk
        assert audit.metadata["proposal_id"] == newer.pk
        assert audit.metadata["note_id"] == self.evaluation.notes.get().pk

    def test_approval_rechecks_period_scale_and_live_lms_access(self):
        proposal = self.deliver()
        for obj, field, changed in (
            (self.period, "cloturee" if self.secondary else "cloture", True),
            (self.evaluation, "bareme", 30),
            (self.enrollment, "is_active", False),
            (self.mapping, "actif", False),
            (self.assessment, "actif", False),
        ):
            with self.subTest(field=field, model=obj._meta.label):
                original = getattr(obj, field)
                setattr(obj, field, changed)
                obj.save(update_fields=[field])
                response = self.review(proposal)
                assert response.status_code in (400, 409), response.data
                assert not self.evaluation.notes.exists()
                proposal.refresh_from_db()
                assert proposal.review_status == "pending"
                setattr(obj, field, original)
                obj.save(update_fields=[field])
        assert self.review(proposal).status_code == 200

    def test_retained_newer_event_blocks_old_proposal_after_access_is_restored(self):
        older = self.deliver("10", timestamp=(timezone.now() - timedelta(minutes=1)).isoformat())
        self.mapping.actif = False
        self.mapping.save(update_fields=["actif"])
        retained = self.deliver("16")
        assert retained.review_status == "retained"
        assert retained.proposed_evaluation_id is None
        self.mapping.actif = True
        self.mapping.save(update_fields=["actif"])
        assert self.review(older).status_code == 409
        assert not self.evaluation.notes.exists()
        fresh = self.deliver("16", timestamp=(timezone.now() + timedelta(minutes=1)).isoformat())
        assert self.review(fresh).status_code == 200
        assert self.evaluation.notes.get().valeur == 16

    def test_rebinding_academic_period_requires_a_fresh_proposal(self):
        proposal = self.deliver(timestamp=(timezone.now() - timedelta(minutes=1)).isoformat())
        new_period = self.create(
            self.period_model,
            **{self.year_field: self.year, **self.period_values, "numero": 2},
        )
        field = "periode" if self.secondary else "semestre"
        if not self.secondary:
            enrollment = self.create(
                "etudiants.InscriptionPedagogique",
                inscription_admin=apps.get_model("etudiants.InscriptionAdministrative").objects.get(
                    etudiant=self.learners[0]
                ),
                semestre=new_period,
                statut="validee",
            )
            enrollment.ues.add(self.subject.ue)
        changed = self.client.patch(self.url, {field: new_period.pk}, format="json")
        assert changed.status_code == 200, changed.data
        refused = self.review(proposal)
        assert refused.status_code == 409, refused.data
        assert not self.evaluation.notes.exists()
        fresh = self.deliver()
        accepted = self.review(fresh)
        assert accepted.status_code == 200, accepted.data

    def test_foreign_and_unrelated_actors_cannot_read_or_review_proposals(self):
        proposal = self.deliver()
        listing = f"{self.url}propositions_lms/"
        self.client.force_authenticate(self.learners[0].user)
        assert self.client.get(listing).status_code == 404
        assert self.review(proposal).status_code == 404
        other_teacher = type(self.teacher).objects.create_user(
            "other-grade-reviewer", role="enseignant", etablissement=self.tenant
        )
        self.client.force_authenticate(other_teacher)
        assert self.client.get(listing).status_code == 404
        assert self.review(proposal).status_code == 404
        other_tenant = type(self.tenant)(schema_name="grade_review_foreign")
        self.setup_tenant(other_tenant)
        other_tenant.auto_create_schema = False
        with schema_context("public"):
            other_tenant.save()
        self.admin.etablissement = other_tenant
        self.admin.save(update_fields=["etablissement"])
        self.client.force_authenticate(self.admin)
        assert self.client.get(listing).status_code == 403
        assert self.review(proposal).status_code == 403
        assert not self.evaluation.notes.exists()

    def test_permission_revocation_and_note_scope_apply_to_review(self):
        proposal = self.deliver()
        self.teacher.role = "comptable"
        self.teacher.save(update_fields=["role"])
        permissions = Permission.objects.filter(
            content_type__app_label="notes",
            codename__in=["view_evaluation", "view_note", "change_note"],
        )
        self.teacher.user_permissions.set(permissions)
        self.client.force_authenticate(type(self.teacher).objects.get(pk=self.teacher.pk))
        listing = self.client.get(f"{self.url}propositions_lms/")
        assert listing.status_code == 200, listing.data
        assert listing.data["results"][0]["id"] == proposal.pk
        self.teacher.attributs_acces = {
            "permission_scopes": {"notes.change_note": {"classes" if self.secondary else "ecues": [-1]}}
        }
        self.teacher.save(update_fields=["attributs_acces"])
        self.client.force_authenticate(type(self.teacher).objects.get(pk=self.teacher.pk))
        assert self.review(proposal).status_code == 403
        self.teacher.attributs_acces = {}
        self.teacher.save(update_fields=["attributs_acces"])
        self.teacher.user_permissions.remove(permissions.get(codename="change_note"))
        self.client.force_authenticate(type(self.teacher).objects.get(pk=self.teacher.pk))
        assert self.review(proposal).status_code == 403
        assert not self.evaluation.notes.exists()

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


class LMSGradeReviewConcurrencyTests(LMSGradeFixture):
    @classmethod
    def _fixture_setup(cls):
        TransactionTestCase._fixture_setup.__func__(cls)

    def _fixture_teardown(self):
        with schema_context(self.tenant.schema_name):
            TransactionTestCase._fixture_teardown(self)
            for record in self.shared_fixture_records:
                record.delete()

    def setUp(self):
        self.shared_fixture_records = []
        super().setUp()
        self.shared_fixture_records = [self.year]
        if self.secondary:
            self.shared_fixture_records.append(self.classe.niveau)
        assert not connection.in_atomic_block

    def test_simultaneous_review_creates_one_official_grade_and_one_decision(self):
        proposal = self.deliver()
        start = Barrier(2)

        def approve():
            try:
                with schema_context(self.tenant.schema_name):
                    actor = type(self.teacher).objects.get(pk=self.teacher.pk)
                    client = APIClient(SERVER_NAME=self.get_test_tenant_domain())
                    client.force_authenticate(actor)
                    start.wait(timeout=10)
                    response = client.post(
                        f"{self.url}examiner_proposition_lms/",
                        {"proposal_id": proposal.pk, "decision": "approve"},
                        format="json",
                    )
                    return response.status_code
            finally:
                connections["default"].close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: approve(), range(2)))
        assert sorted(results) == [200, 409]
        assert self.evaluation.notes.count() == 1
        assert self.evaluation.notes.get().valeur == 12
        assert apps.get_model("core.WorkflowEvent").objects.filter(action="lms_grade_review").count() == 1
        proposal.refresh_from_db()
        assert proposal.review_status == "approved"
        assert proposal.reviewed_by_id == self.teacher.pk
