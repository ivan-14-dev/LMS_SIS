"""Durable SIS state with simulated remote HTTP outcomes (both variants)."""

from datetime import timedelta
from unittest.mock import Mock, patch

import pytest
import requests
from apps.integration.models import EdxAccessIntent, EdxEnrollment, OutboxEvent
from apps.integration.sync_service import SyncService
from apps.integration.tasks import _publish_outbox_events_for_current_schema
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.integration.tests.test_sync_service import EnrollmentFixtureMixin
from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.utils import timezone

from sis_common.lms_access_sync import learner_model, queue_access
from sis_common.lms_receipts import confirm_account, update_enrollment_receipts


class WorkerInterrupted(BaseException):
    pass


class LMSDeliveryTests(EnrollmentFixtureMixin, TenantAPITestCase):
    def setUp(self):
        super().setUp()
        self.remote = Mock()
        self.factory = self.enterContext(
            patch("apps.integration.sync_service.get_edx_client", return_value=self.remote)
        )
        self.learner_class, self.learner_field = learner_model()
        self.learner = self.learner_class.objects.get(user=self.user)
        self.remote.create_user.return_value = {"id": 505}
        self.remote.set_course_access.return_value = {"id": 606}

    def expire(self, event):
        OutboxEvent.objects.filter(pk=event.pk).update(derniere_tentative=timezone.now() - timedelta(minutes=11))

    def test_user_intent_survives_worker_interruption_before_mapping_confirmation(self):
        def interrupted(**kwargs):
            event = OutboxEvent.objects.get(event_type="user.sync")
            assert event.statut == "processing"
            assert event.payload == {"role": "student"}
            raise WorkerInterrupted()

        self.remote.create_user.side_effect = interrupted
        with pytest.raises(WorkerInterrupted):
            SyncService().sync_user_to_lms(self.user)
        event = OutboxEvent.objects.get(event_type="user.sync")
        assert event.statut == "processing"
        self.user_mapping.refresh_from_db()
        assert self.user_mapping.user_id_edx is None
        self.expire(event)
        self.remote.create_user.side_effect = None
        assert _publish_outbox_events_for_current_schema() == 1
        event.refresh_from_db()
        assert event.statut == "done"
        assert event.erreur == ""
        assert OutboxEvent.objects.count() == 1
        self.user_mapping.refresh_from_db()
        assert self.user_mapping.user_id_edx == 505
        assert self.remote.create_user.call_args_list[0] == self.remote.create_user.call_args_list[1]
        assert _publish_outbox_events_for_current_schema() == 0

    def test_course_intent_survives_lost_response_with_same_identity_and_version(self):
        course = self.course_mapping
        if self.learner_field == "eleve":
            args = (course.matiere, course.classe, "Replayed course")
        else:
            args = (course.ecue, course.ecue.ue.semestre.annee_universitaire, "Replayed course")
        self.remote.update_course.side_effect = WorkerInterrupted()
        with pytest.raises(WorkerInterrupted):
            SyncService().sync_course_to_cms(*args)
        event = OutboxEvent.objects.get(event_type="course.create")
        requested = event.payload["requested_at"]
        self.expire(event)
        self.remote.update_course.side_effect = None
        self.remote.update_course.return_value = {"id": course.course_id, "display_name": "Replayed course"}
        assert _publish_outbox_events_for_current_schema() == 1
        course.refresh_from_db()
        assert course.last_sync_requested_at.isoformat() == requested
        assert self.remote.update_course.call_args_list[0] == self.remote.update_course.call_args_list[1]
        assert OutboxEvent.objects.get(pk=event.pk).statut == "done"

    def test_missing_configuration_releases_claim_with_backoff_instead_of_sticking_processing(self):
        event = OutboxEvent.objects.create(
            event_type="user.sync",
            aggregate_type="user",
            aggregate_id=str(self.user.pk),
            payload={"role": "student"},
            nb_tentatives=8,
        )
        self.factory.side_effect = ImproperlyConfigured("LMS unavailable")
        assert _publish_outbox_events_for_current_schema() == 1
        event.refresh_from_db()
        assert event.statut == "pending"
        assert event.nb_tentatives == 9
        assert _publish_outbox_events_for_current_schema() == 0
        self.expire(event)
        self.factory.side_effect = None
        assert _publish_outbox_events_for_current_schema() == 1
        assert OutboxEvent.objects.get(pk=event.pk).statut == "done"

    def test_api_unconfigured_provider_returns_503_and_retains_identity_request(self):
        admin = get_user_model().objects.create_user(
            username="lms-unavailable-admin",
            is_staff=True,
            etablissement=self.tenant,
        )
        self.client.force_authenticate(admin)
        self.factory.side_effect = ImproperlyConfigured("LMS unavailable")
        response = self.client.post(f"/api/v1/integration/sync/user/{self.user.pk}/", {}, format="json")
        assert response.status_code == 503
        assert response.data["available"] is False
        assert OutboxEvent.objects.get(event_type="user.sync").statut == "pending"
        self.remote.create_user.assert_not_called()

    def test_http_outage_does_not_exhaust_provisioning_after_five_attempts(self):
        event = OutboxEvent.objects.create(
            event_type="user.sync",
            aggregate_type="user",
            aggregate_id=str(self.user.pk),
            payload={"role": "student"},
            nb_tentatives=8,
        )
        self.remote.create_user.side_effect = requests.ConnectionError("Simulated outage")
        assert _publish_outbox_events_for_current_schema() == 1
        event.refresh_from_db()
        assert event.statut == "pending"
        assert event.nb_tentatives == 9

    def test_identity_receipt_cannot_rebind_or_reactivate_a_sis_mapping(self):
        model = type(self.user_mapping)
        username = self.user_mapping.username_edx
        assert confirm_account(model, {"data": {"user": {"username": username, "id": 505}}})
        assert not confirm_account(model, {"user": {"username": username, "id": 506}})
        assert not confirm_account(model, {"user": {"username": self.user.username, "id": 507}})
        self.user_mapping.refresh_from_db()
        self.user_mapping.actif = False
        self.user_mapping.save(update_fields=["actif"])
        assert not confirm_account(model, {"user": {"username": username, "id": 505}})
        self.user_mapping.refresh_from_db()
        assert not self.user_mapping.actif
        assert self.user_mapping.user_id_edx == 505
        assert model.objects.count() == 1

    def test_suspension_queues_withdrawal_and_late_receipt_cannot_reactivate(self):
        service = SyncService()
        service.sync_enrollment_to_lms(self.learner, self.course_mapping)
        self.learner.statut = "suspendu"
        self.learner.save(update_fields=["statut"])
        assert _publish_outbox_events_for_current_schema() == 1
        assert not self.remote.set_course_access.call_args.kwargs["active"]
        assert not EdxAccessIntent.objects.get().is_active
        queryset = EdxEnrollment.objects.filter(course=self.course_mapping)
        assert not update_enrollment_receipts(queryset, self.learner_field, True)
        assert not queryset.get().is_active
        with pytest.raises(ValueError, match="scolarité"):
            queue_access(self.user, self.course_mapping, kind="enrollment", active=True)

    def test_withdrawal_intent_blocks_late_enrollment_even_when_learner_still_active(self):
        SyncService().sync_enrollment_to_lms(self.learner, self.course_mapping, active=False)
        queryset = EdxEnrollment.objects.filter(course=self.course_mapping)
        assert not update_enrollment_receipts(queryset, self.learner_field, True)
        assert not queryset.get().is_active

    def test_suspended_annual_registration_blocks_access_even_with_active_learner(self):
        course = self.course_mapping
        if self.learner_field == "eleve":
            model = apps.get_model("eleves", "Inscription")
            values = {
                "eleve": self.learner,
                "classe": course.classe,
                "annee_scolaire": course.classe.annee_scolaire,
            }
        else:
            model = apps.get_model("etudiants", "InscriptionAdministrative")
            values = {
                "etudiant": self.learner,
                "formation": course.ecue.ue.maquette.formation,
                "annee_universitaire": course.ecue.ue.semestre.annee_universitaire,
            }
        registration = model.objects.create(**values, date_inscription="2026-09-01", statut="validee")
        SyncService().sync_enrollment_to_lms(self.learner, course)
        registration.statut = "suspendue"
        registration.save(update_fields=["statut"])
        assert _publish_outbox_events_for_current_schema() == 1
        assert not EdxEnrollment.objects.get().is_active
        with pytest.raises(ValueError, match="scolarité"):
            queue_access(self.user, course, kind="enrollment", active=True)

    def test_class_transfer_with_valid_registration_withdraws_previous_course(self):
        if self.learner_field != "eleve":
            self.skipTest("School class assignment is specific to the secondary SIS.")
        course = self.course_mapping
        registration = apps.get_model("eleves", "Inscription").objects.create(
            eleve=self.learner,
            classe=course.classe,
            annee_scolaire=course.classe.annee_scolaire,
            date_inscription="2026-09-01",
            statut="validee",
        )
        SyncService().sync_enrollment_to_lms(self.learner, course)
        other_class = type(course.classe).objects.create(
            etablissement=self.tenant,
            annee_scolaire=course.classe.annee_scolaire,
            niveau=course.classe.niveau,
            nom="Transferred class",
        )
        registration.classe = other_class
        registration.save(update_fields=["classe"])
        assert _publish_outbox_events_for_current_schema() == 1
        assert not EdxEnrollment.objects.get().is_active
