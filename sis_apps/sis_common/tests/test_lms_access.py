from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event
from unittest import TestCase
from unittest.mock import Mock, create_autospec, patch
from uuid import uuid4

import requests
from apps.integration.edx_client import EdxClient
from apps.integration.models import EdxAccessIntent, EdxEnrollment, OutboxEvent
from apps.integration.sync_service import SyncService
from apps.integration.tasks import _claim_pending_outbox_events, _publish_outbox_events_for_current_schema
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.integration.tests.test_sync_service import EnrollmentFixtureMixin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import connection, connections, transaction
from django.test import TransactionTestCase
from django.utils import timezone
from django_tenants.utils import schema_context

from sis_common.lms_access_sync import (
    learner_model,
    queue_access,
    queue_revoked_access,
    recover_interrupted_access,
    save_claimed_outbox_event,
)


class LMSAccessTransportTests(TestCase):
    def setUp(self):
        self.client = EdxClient(
            lms_url="https://lms.example.test",
            cms_url="https://studio.example.test",
            oauth_client_id="synthetic-client",
            oauth_client_secret="synthetic-secret",
        )
        self.client._access_token = "synthetic-token"
        self.client._token_expires_at = float("inf")
        self.key = "course-v1:SIS+access+sis"
        self.when = timezone.now()
        self.payload = {
            "course_id": self.key,
            "username": "synthetic-learner",
            "kind": "enrollment",
            "is_active": True,
            "requested_at": self.when.isoformat(),
            "id": 12,
        }

    def call(self, **changes):
        arguments = {
            "course_key": self.key,
            "username": "synthetic-learner",
            "kind": "enrollment",
            "active": True,
            "requested_at": self.when,
            **changes,
        }
        return self.client.set_course_access(**arguments)

    @patch("sis_common.lms_access.requests.post")
    def test_scoped_transport_preserves_tls_and_disables_redirects(self, post):
        post.return_value = Mock(status_code=200)
        post.return_value.json.return_value = self.payload
        self.assertEqual(self.call(), self.payload)
        post.assert_called_once_with(
            f"https://lms.example.test/api/sis/v1/courses/{self.key}/enrollments/synthetic-learner/",
            json={"is_active": True, "requested_at": self.when.isoformat()},
            headers=self.client._headers(),
            timeout=30,
            verify=True,
            allow_redirects=False,
        )

    @patch("sis_common.lms_access.requests.post")
    def test_wrong_identity_state_or_revision_is_not_a_confirmation(self, post):
        post.return_value = Mock(status_code=200)
        for changes in (
            {"username": "other-learner"},
            {"course_id": "course-v1:SIS+other+sis"},
            {"is_active": False},
            {"kind": "teaching"},
            {"id": True},
            {"requested_at": (self.when - timedelta(seconds=1)).isoformat()},
        ):
            post.return_value.json.return_value = {**self.payload, **changes}
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.call()
        post.return_value.status_code = 302
        with self.assertRaises(ValueError):
            self.call()

    @patch("sis_common.lms_access.requests.post")
    def test_invalid_requests_never_leave_the_sis(self, post):
        for changes in (
            {"username": "../other"},
            {"active": "false"},
            {"kind": "instructor"},
            {"course_key": "course-v1:SIS+access+sis/other"},
            {"requested_at": "2026-01-01"},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.call(**changes)
        post.assert_not_called()


class LMSAccessDecisionTests(EnrollmentFixtureMixin, TenantAPITestCase):
    def setUp(self):
        super().setUp()
        _, self.learner_field = learner_model()
        self.learner = getattr(self, self.learner_field)
        self.remote = create_autospec(EdxClient, instance=True)
        self.remote.set_course_access.return_value = {"id": 12}
        self.enterContext(patch("apps.integration.sync_service.get_edx_client", return_value=self.remote))
        self.service = SyncService()

    def sync(self, active=True, **options):
        return self.service.sync_enrollment_to_lms(self.learner, self.course_mapping, active=active, **options)

    def test_failed_grant_cannot_reactivate_a_newer_withdrawal(self):
        self.remote.set_course_access.side_effect = requests.ConnectionError("response lost")
        with self.assertRaises(requests.ConnectionError):
            self.sync()
        earlier = OutboxEvent.objects.get(event_type="access.set")
        self.remote.set_course_access.side_effect = None
        enrollment = self.sync(False)
        self.remote.reset_mock()
        self.assertFalse(enrollment.is_active)
        self.assertEqual(_publish_outbox_events_for_current_schema(), 1)
        self.remote.set_course_access.assert_not_called()
        earlier.refresh_from_db()
        self.assertEqual(earlier.statut, "done")
        self.assertEqual(EdxAccessIntent.objects.count(), 1)

    def test_lost_response_reuses_the_persisted_decision(self):
        self.remote.set_course_access.side_effect = requests.Timeout("response lost")
        with self.assertRaises(requests.Timeout):
            self.sync()
        requested = self.remote.set_course_access.call_args.kwargs["requested_at"]
        self.remote.set_course_access.side_effect = None
        self.assertEqual(_publish_outbox_events_for_current_schema(), 1)
        self.assertEqual(self.remote.set_course_access.call_args.kwargs["requested_at"], requested)
        intent = EdxAccessIntent.objects.get()
        self.assertEqual(intent.applied_requested_at, requested)
        self.assertEqual(EdxEnrollment.objects.count(), 1)
        self.assertEqual(_publish_outbox_events_for_current_schema(), 0)

    def test_remote_conflict_requires_an_explicit_new_decision(self):
        response = requests.Response()
        response.status_code = 409
        self.remote.set_course_access.side_effect = requests.HTTPError("native access changed", response=response)
        with self.assertRaises(requests.HTTPError):
            self.sync()
        event = OutboxEvent.objects.get(event_type="access.set")
        self.assertEqual(event.statut, "dead")
        self.assertIn("native access changed", event.erreur)
        self.assertEqual(_publish_outbox_events_for_current_schema(), 0)
        self.assertFalse(EdxEnrollment.objects.exists())

    def test_revocation_removes_access_without_reactivating_the_local_account(self):
        self.sync()
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        self.assertEqual(_publish_outbox_events_for_current_schema(), 1)
        self.assertFalse(self.remote.set_course_access.call_args.kwargs["active"])
        self.assertFalse(EdxEnrollment.objects.get().is_active)
        self.assertFalse(EdxAccessIntent.objects.get().is_active)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)
        with self.assertRaisesRegex(ValueError, "révoquée"):
            self.sync()

    def test_deleted_learner_record_still_allows_withdrawal(self):
        self.sync()
        self.learner.delete()
        self.assertEqual(_publish_outbox_events_for_current_schema(), 1)
        self.assertFalse(self.remote.set_course_access.call_args.kwargs["active"])
        self.assertFalse(EdxEnrollment.objects.exists())
        self.assertFalse(type(self.learner).objects.exists())

    def test_teacher_assignment_is_course_scoped_and_withdrawn_after_role_change(self):
        with self.assertRaisesRegex(ValueError, "enseignant"):
            self.service.sync_teaching_to_lms(self.user, self.course_mapping, active=True)
        self.user.role = "enseignant"
        self.user.save(update_fields=["role"])
        intent = self.service.sync_teaching_to_lms(self.user, self.course_mapping, active=True)
        self.assertEqual(intent.kind, "teaching")
        self.assertFalse(EdxEnrollment.objects.exists())
        self.user.role = self.learner_field
        self.user.save(update_fields=["role"])
        queue_revoked_access()
        self.assertEqual(_publish_outbox_events_for_current_schema(), 1)
        self.assertEqual(self.remote.set_course_access.call_args.kwargs["kind"], "teaching")
        self.assertFalse(self.remote.set_course_access.call_args.kwargs["active"])
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_staff or self.user.is_superuser)

    def test_teaching_withdrawal_survives_more_than_five_transient_failures_with_backoff(self):
        self.user.role = "enseignant"
        self.user.save(update_fields=["role"])
        self.service.sync_teaching_to_lms(self.user, self.course_mapping, active=True)
        self.user.role = self.learner_field
        self.user.save(update_fields=["role"])
        self.remote.set_course_access.side_effect = requests.ConnectionError("LMS unavailable")
        for _attempt in range(6):
            self.assertEqual(_publish_outbox_events_for_current_schema(), 1)
            event = OutboxEvent.objects.get(statut="pending")
            self.assertEqual(_publish_outbox_events_for_current_schema(), 0)
            OutboxEvent.objects.filter(pk=event.pk).update(derniere_tentative=timezone.now() - timedelta(minutes=6))
        intent = EdxAccessIntent.objects.get()
        requested = intent.requested_at
        self.assertFalse(intent.is_active)
        self.assertNotEqual(intent.applied_requested_at, requested)
        self.remote.set_course_access.side_effect = None
        self.assertEqual(_publish_outbox_events_for_current_schema(), 1)
        intent.refresh_from_db()
        event.refresh_from_db()
        self.assertEqual(intent.applied_requested_at, requested)
        self.assertEqual(event.statut, "done")
        self.assertEqual(event.nb_tentatives, 6)
        self.assertEqual(self.remote.set_course_access.call_args.kwargs["requested_at"], requested)
        self.assertFalse(self.remote.set_course_access.call_args.kwargs["active"])

    def test_permanent_withdrawal_conflict_remains_visible_without_automatic_override(self):
        self.sync()
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        response = requests.Response()
        response.status_code = 409
        self.remote.set_course_access.side_effect = requests.HTTPError("native conflict", response=response)
        self.assertEqual(_publish_outbox_events_for_current_schema(), 1)
        self.assertEqual(OutboxEvent.objects.get(statut="dead").nb_tentatives, 1)
        self.assertEqual(_publish_outbox_events_for_current_schema(), 0)
        self.assertTrue(EdxEnrollment.objects.get().is_active)

    def test_revocation_scan_rechecks_eligibility_under_lock(self):
        self.sync()
        original = EdxAccessIntent.objects.get()
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])

        def reactivated_before_lock(*args, **kwargs):
            get_user_model().objects.filter(pk=self.user.pk).update(is_active=True)
            return queue_access(*args, **kwargs)

        with patch("sis_common.lms_access_sync.queue_access", side_effect=reactivated_before_lock):
            queue_revoked_access()
        current = EdxAccessIntent.objects.get()
        self.assertTrue(current.is_active)
        self.assertEqual(current.requested_at, original.requested_at)
        self.assertFalse(OutboxEvent.objects.filter(statut="pending").exists())

    def test_historical_request_does_not_override_a_newer_explicit_decision(self):
        self.sync(False)
        intent = EdxAccessIntent.objects.get()
        self.remote.reset_mock()
        result, event = queue_access(
            self.user,
            self.course_mapping,
            kind="enrollment",
            active=True,
            requested_at=intent.requested_at - timedelta(seconds=1),
        )
        self.assertEqual(result.pk, intent.pk)
        self.assertIsNone(event)
        self.remote.set_course_access.assert_not_called()

    def test_non_audit_legacy_event_is_visible_but_not_silently_converted(self):
        event = OutboxEvent.objects.create(
            event_type="enrollment.create",
            aggregate_type=self.learner_field,
            aggregate_id=str(self.learner.pk),
            payload={"course_mapping_id": self.course_mapping.pk, "mode": "honor"},
        )
        self.assertEqual(_publish_outbox_events_for_current_schema(), 1)
        event.refresh_from_db()
        self.assertEqual(event.statut, "dead")
        self.assertIn("audit", event.erreur)
        self.remote.set_course_access.assert_not_called()

    def admin(self):
        user = get_user_model().objects.create_user(
            "access-administrator",
            email="access-administrator@example.test",
            is_staff=True,
            role="admin",
            etablissement=self.tenant,
        )
        user.user_permissions.add(
            Permission.objects.get(content_type__app_label="integration", codename="change_edxaccessintent")
        )
        self.client.force_authenticate(user)
        return user

    def assert_staff_cannot_assign_access(self, *, kind):
        teaching = kind == "teaching"
        if teaching:
            self.user.role = "enseignant"
            self.user.save(update_fields=["role"])
        payload = {
            "user_id" if teaching else f"{self.learner_field}_id": self.user.pk if teaching else self.learner.pk,
            "course_mapping_id": self.course_mapping.pk,
        }
        for role in ("enseignant", "comptable"):
            actor = get_user_model().objects.create_user(
                f"staff-access-{role}", is_staff=True, role=role, etablissement=self.tenant
            )
            self.client.force_authenticate(actor)
            response = self.client.post(
                f"/api/v1/integration/sync/{'teaching' if teaching else 'enroll'}/", payload, format="json"
            )
            assert response.status_code == 403, response.data
        self.remote.set_course_access.assert_not_called()
        assert not EdxAccessIntent.objects.exists()
        assert not OutboxEvent.objects.exists()

    def test_staff_cannot_assign_lms_enrollments(self):
        self.assert_staff_cannot_assign_access(kind="enrollment")

    def test_staff_cannot_assign_lms_teaching(self):
        self.assert_staff_cannot_assign_access(kind="teaching")

    def test_access_permission_obeys_course_scope_and_revocation_without_staff(self):
        actor = self.admin()
        permission = "integration.change_edxaccessintent"
        payload = {f"{self.learner_field}_id": self.learner.pk, "course_mapping_id": self.course_mapping.pk}
        url = "/api/v1/integration/sync/enroll/"
        for constraints in ({"courses": []}, {"unknown": [self.course_mapping.pk]}):
            actor.attributs_acces = {"permission_scopes": {permission: constraints}}
            actor.save(update_fields=["attributs_acces"])
            assert self.client.post(url, payload, format="json").status_code == 403
        self.remote.set_course_access.assert_not_called()
        assert not EdxAccessIntent.objects.exists()
        actor.is_staff = False
        actor.attributs_acces = {"permission_scopes": {permission: {"courses": [self.course_mapping.pk]}}}
        actor.save(update_fields=["is_staff", "attributs_acces"])
        assert self.client.post(url, payload, format="json").status_code == 200
        intent = EdxAccessIntent.objects.get()
        requested_at = intent.requested_at
        self.remote.reset_mock()
        actor.user_permissions.clear()
        self.client.force_authenticate(get_user_model().objects.get(pk=actor.pk))
        assert self.client.post(url, {**payload, "active": False}, format="json").status_code == 403
        self.remote.set_course_access.assert_not_called()
        intent.refresh_from_db()
        assert intent.is_active
        assert intent.requested_at == requested_at

    def test_api_validates_payload_permissions_and_explicit_withdrawal(self):
        url = "/api/v1/integration/sync/enroll/"
        payload = {f"{self.learner_field}_id": self.learner.pk, "course_mapping_id": self.course_mapping.pk}
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.post(url, payload, format="json").status_code, 403)
        self.admin()
        for changes in ({"active": "false"}, {"mode": "verified"}, {"requested_at": timezone.now().isoformat()}):
            with self.subTest(changes=changes):
                self.assertEqual(self.client.post(url, {**payload, **changes}, format="json").status_code, 400)
        self.remote.set_course_access.assert_not_called()
        self.assertEqual(self.client.post(url, payload, format="json").status_code, 200)
        response = self.client.post(url, {**payload, "active": False}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["is_active"])
        self.assertFalse(EdxEnrollment.objects.get().is_active)

    def test_api_teaching_and_unavailable_lms_do_not_report_false_success(self):
        self.admin()
        payload = {"user_id": self.user.pk, "course_mapping_id": self.course_mapping.pk}
        url = "/api/v1/integration/sync/teaching/"
        self.assertEqual(self.client.post(url, payload, format="json").status_code, 409)
        self.user.role = "enseignant"
        self.user.save(update_fields=["role"])
        self.remote.set_course_access.side_effect = requests.ConnectionError("unavailable")
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, 502)
        self.assertEqual(OutboxEvent.objects.get().statut, "pending")
        self.assertIsNone(EdxAccessIntent.objects.get().applied_requested_at)

    @patch("apps.integration.edx_client.get_edx_client")
    def test_publication_api_requires_admin_review_and_an_active_course(self, get_client):
        get_client.return_value = self.remote
        url = f"/api/v1/integration/sync/course/{self.course_mapping.pk}/publication/"
        payload = {"expected_revision": "1" * 24, "operation_id": str(uuid4()), "confirm": True}
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(url, payload, format="json").status_code, 403)
        self.admin()
        self.remote.get_course_revision.return_value = {
            "id": self.course_mapping.course_id,
            "revision": payload["expected_revision"],
        }
        self.assertEqual(self.client.get(url).status_code, 200)
        for changes in ({"confirm": "true"}, {"start": "2000-01-01"}, {"expected_revision": "latest"}):
            with self.subTest(changes=changes):
                self.assertEqual(self.client.post(url, {**payload, **changes}, format="json").status_code, 400)
        self.remote.publish_course.assert_not_called()
        self.remote.publish_course.return_value = {
            "id": self.course_mapping.course_id,
            "revision": payload["expected_revision"],
            "operation_id": payload["operation_id"],
            "published_version": "2" * 24,
        }
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["published_version"], "2" * 24)
        self.course_mapping.actif = False
        self.course_mapping.save(update_fields=["actif"])
        self.assertEqual(self.client.get(url).status_code, 409)
        self.assertEqual(self.client.post(url, payload, format="json").status_code, 409)
        self.remote.publish_course.assert_called_once()

    @patch("apps.integration.edx_client.get_edx_client")
    def test_publication_api_reports_conflicts_and_unconfirmed_responses(self, get_client):
        get_client.return_value = self.remote
        self.admin()
        url = f"/api/v1/integration/sync/course/{self.course_mapping.pk}/publication/"
        payload = {"expected_revision": "1" * 24, "operation_id": str(uuid4()), "confirm": True}
        remote_response = requests.Response()
        remote_response.status_code = 409
        for error, expected in (
            (requests.HTTPError("Draft changed", response=remote_response), 409),
            (requests.Timeout("Response lost"), 502),
            (ValueError("Invalid confirmation"), 502),
        ):
            self.remote.publish_course.side_effect = error
            with self.subTest(error=type(error).__name__):
                response = self.client.post(url, payload, format="json")
                self.assertEqual(response.status_code, expected)
                self.assertIn("error", response.data)


class LMSAccessWorkerRecoveryTests(EnrollmentFixtureMixin, TenantAPITestCase):
    @classmethod
    def _fixture_setup(cls):
        TransactionTestCase._fixture_setup.__func__(cls)

    def _fixture_teardown(self):
        with schema_context(self.tenant.schema_name):
            TransactionTestCase._fixture_teardown(self)
            # Shared calendars are outside the tenant-schema flush.
            for record in self.shared_fixture_records:
                record.delete()

    def setUp(self):
        self.shared_fixture_records = []
        super().setUp()
        if learner_model()[1] == "eleve":
            self.shared_fixture_records = [self.classe.annee_scolaire, self.classe.niveau]
        else:
            self.shared_fixture_records = [self.course_mapping.ecue.ue.maquette.annee_universitaire]
        self.remote = create_autospec(EdxClient, instance=True)
        self.remote.set_course_access.return_value = {"id": 12}
        self.enterContext(patch("apps.integration.sync_service.get_edx_client", return_value=self.remote))

    def claim(self):
        intent, _ = queue_access(self.user, self.course_mapping, kind="enrollment", active=True)
        event = _claim_pending_outbox_events(batch_size=1)[0]
        return intent, event

    def test_expired_claim_is_not_stolen_while_native_application_holds_the_intent_lock(self):
        self.assertFalse(connection.in_atomic_block)
        intent, event = self.claim()
        OutboxEvent.objects.filter(pk=event.pk).update(derniere_tentative=timezone.now() - timedelta(minutes=11))
        locked, release = Event(), Event()

        def native_call_in_progress():
            try:
                with schema_context(self.tenant.schema_name), transaction.atomic():
                    EdxAccessIntent.objects.select_for_update().get(pk=intent.pk)
                    locked.set()
                    if not release.wait(timeout=15):
                        raise TimeoutError("The test did not release its synthetic native call")
            finally:
                connections["default"].close()

        with ThreadPoolExecutor(max_workers=1) as pool:
            running = pool.submit(native_call_in_progress)
            try:
                self.assertTrue(locked.wait(timeout=10))
                self.assertEqual(recover_interrupted_access(), 0)
                event.refresh_from_db()
                self.assertEqual(event.statut, "processing")
            finally:
                release.set()
            running.result(timeout=10)
        self.assertEqual(_publish_outbox_events_for_current_schema(), 1)
        event.refresh_from_db()
        intent.refresh_from_db()
        self.assertEqual(event.statut, "done")
        self.assertEqual(intent.applied_requested_at, intent.requested_at)
        self.remote.set_course_access.assert_called_once()

    def test_late_completion_cannot_overwrite_a_reclaimed_event(self):
        _, old_claim = self.claim()
        self.assertEqual(recover_interrupted_access(), 0)
        OutboxEvent.objects.filter(pk=old_claim.pk).update(derniere_tentative=timezone.now() - timedelta(minutes=11))
        old_claim.refresh_from_db()
        self.assertEqual(recover_interrupted_access(), 1)
        new_claim = _claim_pending_outbox_events(batch_size=1)[0]
        old_claim.statut = "dead"
        old_claim.erreur = "Late failure from the interrupted worker"
        self.assertFalse(save_claimed_outbox_event(old_claim))
        new_claim.refresh_from_db()
        self.assertEqual(new_claim.statut, "processing")
        new_claim.statut = "done"
        self.assertTrue(save_claimed_outbox_event(new_claim))
        self.assertFalse(save_claimed_outbox_event(old_claim))
        new_claim.refresh_from_db()
        self.assertEqual(new_claim.statut, "done")
