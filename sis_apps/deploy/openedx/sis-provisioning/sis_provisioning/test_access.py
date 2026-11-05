from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import connection
from django.test import TestCase, override_settings
from django.utils import timezone
from opaque_keys.edx.keys import CourseKey
from rest_framework.test import APIClient

from common.djangoapps.student.models import CourseEnrollment
from common.djangoapps.student.roles import CourseInstructorRole, CourseStaffRole

from .models import ManagedAccess, ManagedAccount, ManagedCourse


@override_settings(ALLOWED_HOSTS=["testserver"], SECURE_SSL_REDIRECT=False)
class AccessProvisioningTests(TestCase):
    def setUp(self):
        self.enterContext(patch.dict(connection.settings_dict, ATOMIC_REQUESTS=False))
        self.manager = get_user_model().objects.create_user("access_service", email="access-service@example.test")
        self.user = get_user_model().objects.create_user("access_learner", email="access-learner@example.test")
        self.manager.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label="sis_provisioning", codename__in=["manage_enrollments", "manage_teaching"]
            )
        )
        self.account = ManagedAccount.objects.create(user=self.user, manager=self.manager, username=self.user.username)
        self.key = CourseKey.from_string("course-v1:SIS_TEST+access+test")
        self.course = ManagedCourse.objects.create(course_id=str(self.key), manager=self.manager, initialized=True)
        CourseInstructorRole(self.key).add_users(self.manager)
        self.native = SimpleNamespace(
            other_course_settings={
                "sis_provisioning": {"binding": str(self.course.ownership_token), "manager": self.manager.pk}
            }
        )
        self.store = self.enterContext(patch("sis_provisioning.access_views.modulestore")).return_value
        self.store.get_course.return_value = self.native
        self.add = self.enterContext(patch("sis_provisioning.access_views.enrollment_api.add_enrollment"))
        self.add.side_effect = self.enroll
        self.update = self.enterContext(patch("sis_provisioning.access_views.enrollment_api.update_enrollment"))
        self.update.side_effect = lambda *args, **kwargs: CourseEnrollment.objects.filter(
            user=self.user, course_id=self.key
        ).update(is_active=kwargs["is_active"])
        self.client = APIClient()
        self.client.force_authenticate(self.manager)
        self.when = timezone.now()

    def enroll(self, *args, **kwargs):
        CourseEnrollment.objects.update_or_create(
            user=self.user, course_id=self.key, defaults={"is_active": True, "mode": "audit"}
        )

    def post(self, active=True, offset=0, kind="enrollments"):
        return self.client.post(
            f"/api/sis/v1/courses/{self.key}/{kind}/{self.user.username}/",
            {"is_active": active, "requested_at": (self.when + timedelta(seconds=offset)).isoformat()},
            format="json",
        )

    def test_grant_replay_and_ordered_withdrawal(self):
        self.assertEqual(self.post().status_code, 200)
        self.assertEqual(self.post().status_code, 200)
        self.add.assert_called_once()
        self.assertEqual(self.post(False, 2).status_code, 200)
        self.assertEqual(self.post(True, 1).status_code, 409)
        self.assertFalse(CourseEnrollment.objects.get(user=self.user, course_id=self.key).is_active)
        self.assertEqual(ManagedAccess.objects.filter(course=self.course).count(), 1)

    def test_disabled_bindings_can_only_withdraw(self):
        self.assertEqual(self.post().status_code, 200)
        self.course.revoked = True
        self.course.save()
        self.user.is_active = False
        self.user.save()
        CourseInstructorRole(self.key).remove_users(self.manager)
        self.assertEqual(self.post(True, 1).status_code, 409)
        self.assertEqual(self.post(False, 2).status_code, 200)
        self.assertFalse(CourseEnrollment.objects.get(user=self.user, course_id=self.key).is_active)

    def test_foreign_course_account_and_service_permission_are_refused(self):
        other = get_user_model().objects.create_user("other_access_service", email="other-access@example.test")
        self.account.manager = other
        self.account.save()
        self.assertEqual(self.post().status_code, 403)
        self.account.manager = self.manager
        self.account.save()
        self.course.manager = other
        self.course.save()
        self.assertEqual(self.post().status_code, 403)
        self.course.manager = self.manager
        self.course.save()
        self.manager.user_permissions.clear()
        self.assertEqual(self.post().status_code, 403)
        self.assertFalse(ManagedAccess.objects.filter(course=self.course).exists())
        self.add.assert_not_called()

    def test_native_manual_withdrawal_is_not_undone_by_replay(self):
        self.assertEqual(self.post().status_code, 200)
        CourseEnrollment.objects.filter(user=self.user, course_id=self.key).update(is_active=False)
        self.assertEqual(self.post().status_code, 409)
        self.add.assert_called_once()
        self.assertEqual(self.post(True, 1).status_code, 200)

    def test_teaching_only_manages_its_course_staff_role(self):
        self.assertEqual(self.post(kind="teaching").status_code, 200)
        self.assertTrue(CourseStaffRole(self.key).has_user(get_user_model().objects.get(pk=self.user.pk)))
        self.assertFalse(CourseInstructorRole(self.key).has_user(get_user_model().objects.get(pk=self.user.pk)))
        self.assertEqual(self.post(False, 2, kind="teaching").status_code, 200)
        self.assertEqual(self.post(True, 1, kind="teaching").status_code, 409)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_staff or self.user.is_superuser)
        self.assertFalse(CourseStaffRole(self.key).has_user(get_user_model().objects.get(pk=self.user.pk)))

    def test_preexisting_teaching_and_paid_enrollment_are_preserved(self):
        CourseStaffRole(self.key).add_users(self.user)
        self.assertEqual(self.post(kind="teaching").status_code, 409)
        self.assertEqual(self.post(False, kind="teaching").status_code, 409)
        CourseEnrollment.objects.create(user=self.user, course_id=self.key, mode="verified", is_active=True)
        self.assertEqual(self.post(False).status_code, 409)
        self.assertTrue(CourseEnrollment.objects.get(user=self.user, course_id=self.key).is_active)

    def assert_unmanaged_audit_remains_untouched(self, initially_active):
        enrollment = CourseEnrollment.objects.create(
            user=self.user, course_id=self.key, mode="audit", is_active=initially_active
        )
        assert self.post().status_code == 409
        assert self.post(False, 1).status_code == 409
        enrollment.refresh_from_db()
        assert enrollment.is_active == initially_active
        assert not ManagedAccess.objects.filter(course=self.course, account=self.account).exists()
        self.add.assert_not_called()
        self.update.assert_not_called()

    def test_preexisting_active_audit_enrollment_is_not_adopted(self):
        self.assert_unmanaged_audit_remains_untouched(True)

    def test_preexisting_inactive_audit_enrollment_is_not_reactivated(self):
        self.assert_unmanaged_audit_remains_untouched(False)

    def test_inactive_teacher_withdrawal_removes_stored_rights_before_reactivation(self):
        self.assertEqual(self.post(kind="teaching").status_code, 200)
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        self.assertEqual(self.post(False, 1, kind="teaching").status_code, 200)
        self.assertEqual(self.post(False, 1, kind="teaching").status_code, 200)
        self.user.is_active = True
        self.user.save(update_fields=["is_active"])
        self.assertFalse(CourseStaffRole(self.key).has_user(get_user_model().objects.get(pk=self.user.pk)))

    def test_unknown_fields_naive_time_and_conflicting_replay_are_refused(self):
        url = f"/api/sis/v1/courses/{self.key}/enrollments/{self.user.username}/"
        for payload in (
            {"is_active": True, "requested_at": "2026-01-01T00:00:00"},
            {"is_active": "false", "requested_at": self.when.isoformat()},
            {"is_active": True, "requested_at": self.when.isoformat(), "is_staff": True},
        ):
            self.assertEqual(self.client.post(url, payload, format="json").status_code, 400)
        self.assertEqual(self.post().status_code, 200)
        self.assertEqual(self.post(False).status_code, 409)
