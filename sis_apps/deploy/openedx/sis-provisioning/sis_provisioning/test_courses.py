from io import StringIO
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import TestCase, override_settings
from opaque_keys.edx.keys import CourseKey
from rest_framework.test import APIClient

from .models import ManagedCourse


@override_settings(ALLOWED_HOSTS=["testserver"], SECURE_SSL_REDIRECT=False)
class CourseProvisioningTests(TestCase):
    def setUp(self):
        # This non-atomic view must not make DRF roll back the fixture transaction.
        self.enterContext(patch.dict(connection.settings_dict, ATOMIC_REQUESTS=False))
        self.manager = get_user_model().objects.create_user(
            "course_provisioning_service", email="course-service@example.test"
        )
        self.permission = Permission.objects.get(
            content_type__app_label="sis_provisioning", codename="provision_courses"
        )
        self.manager.user_permissions.add(self.permission)
        self.client = APIClient()
        self.client.force_authenticate(self.manager)
        self.key = CourseKey.from_string("course-v1:SIS_TEST+qualification+test")
        self.url = f"/api/sis/v1/courses/{self.key}/"
        self.payload = {"display_name": "Synthetic Course"}
        self.courses = {}
        self.store = Mock()
        self.store.get_course.side_effect = lambda key: self.courses.get(str(key))
        self.store.has_course.side_effect = lambda key, **kwargs: str(key) in self.courses
        self.store.update_item.side_effect = lambda course, user_id: course
        self.patch("modulestore", return_value=self.store)
        self.creation_rights = self.patch("is_content_creator", return_value=True)
        self.authoring_rights = self.patch("has_studio_write_access", return_value=True)
        self.create = self.patch("create_new_course", side_effect=self.create_course)
        self.resume = self.patch("resume_initialization")

    def patch(self, name, **kwargs):
        patcher = patch(f"sis_provisioning.course_views.{name}", **kwargs)
        mock = patcher.start()
        self.addCleanup(patcher.stop)
        return mock

    def create_course(self, user, org, number, run, fields):
        course = SimpleNamespace(id=self.key, **fields)
        self.courses[str(self.key)] = course
        return course

    def provision(self):
        response = self.client.post(self.url, self.payload, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        return response

    def test_creation_retry_and_rename_preserve_one_course(self):
        self.provision()
        again = self.client.post(self.url, self.payload, format="json")
        self.assertEqual(again.status_code, 200, again.data)
        self.assertEqual(again.data["id"], str(self.key))
        renamed = self.client.patch(self.url, {"display_name": "Renamed Course"}, format="json")
        self.assertEqual(renamed.status_code, 200, renamed.data)
        self.assertEqual(self.client.get(self.url).data["display_name"], "Renamed Course")
        self.assertEqual(ManagedCourse.objects.filter(course_id=str(self.key)).count(), 1)
        self.create.assert_called_once()
        self.resume.assert_not_called()
        self.manager.refresh_from_db()
        self.assertFalse(self.manager.is_staff or self.manager.is_superuser)
        self.assertEqual(self.courses[str(self.key)].catalog_visibility, "none")

    def test_native_initialization_failure_keeps_ownership_for_safe_retry(self):
        def interrupted(*args):
            self.create_course(*args)
            raise RuntimeError("interrupted after MongoDB creation")

        self.create.side_effect = interrupted
        with self.assertRaisesRegex(RuntimeError, "MongoDB"):
            self.client.post(self.url, self.payload, format="json")
        binding = ManagedCourse.objects.get(course_id=str(self.key))
        self.assertFalse(binding.initialized)
        response = self.client.post(self.url, self.payload, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        binding.refresh_from_db()
        self.assertTrue(binding.initialized)
        self.create.assert_called_once()
        self.resume.assert_called_once()

    def test_existing_unmanaged_course_is_not_adopted(self):
        self.courses[str(self.key)] = SimpleNamespace(id=self.key, display_name="Existing")
        response = self.client.post(self.url, self.payload, format="json")
        self.assertEqual(response.status_code, 409)
        self.assertFalse(ManagedCourse.objects.filter(course_id=str(self.key)).exists())
        self.create.assert_not_called()

    def test_revoked_or_foreign_binding_is_not_changed(self):
        self.provision()
        binding = ManagedCourse.objects.get(course_id=str(self.key))
        binding.revoked = True
        binding.save(update_fields=["revoked"])
        self.assertEqual(self.client.post(self.url, self.payload, format="json").status_code, 409)
        binding.revoked = False
        other = get_user_model().objects.create_user("other_course_service", email="other-course-service@example.test")
        binding.manager = other
        binding.save(update_fields=["manager", "revoked"])
        self.assertEqual(self.client.patch(self.url, self.payload, format="json").status_code, 403)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_deleted_or_replaced_course_is_not_recreated(self):
        self.provision()
        course = self.courses.pop(str(self.key))
        self.assertEqual(self.client.post(self.url, self.payload, format="json").status_code, 409)
        self.create.assert_called_once()
        course.other_course_settings = {}
        self.courses[str(self.key)] = course
        self.assertEqual(self.client.post(self.url, self.payload, format="json").status_code, 409)
        self.store.update_item.assert_not_called()

    def test_revoked_authoring_rights_are_not_regranted(self):
        self.provision()
        self.authoring_rights.return_value = False
        self.assertEqual(self.client.post(self.url, self.payload, format="json").status_code, 403)
        self.resume.assert_not_called()
        self.store.update_item.assert_not_called()

    def test_read_rechecks_revoked_service_permission(self):
        self.provision()
        self.manager.user_permissions.clear()
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_service_and_native_creation_permissions_are_required(self):
        self.creation_rights.return_value = False
        self.assertEqual(self.client.post(self.url, self.payload, format="json").status_code, 403)
        self.creation_rights.return_value = True
        self.manager.user_permissions.clear()
        self.assertEqual(self.client.post(self.url, self.payload, format="json").status_code, 403)
        self.client.force_authenticate(None)
        self.assertIn(self.client.post(self.url, self.payload, format="json").status_code, (401, 403))
        self.create.assert_not_called()
        self.assertFalse(ManagedCourse.objects.filter(course_id=str(self.key)).exists())

    def test_unknown_fields_and_unknown_patch_are_rejected(self):
        for payload in ({}, {"display_name": ""}, {**self.payload, "start": "2000-01-01"}, []):
            with self.subTest(payload=payload):
                self.assertEqual(self.client.post(self.url, payload, format="json").status_code, 400)
        self.assertEqual(self.client.patch(self.url, self.payload, format="json").status_code, 404)
        self.create.assert_not_called()

    def test_historical_binding_requires_confirmation_and_existing_authoring_access(self):
        course = SimpleNamespace(id=self.key, display_name="Historical", other_course_settings={"existing": "value"})
        self.courses[str(self.key)] = course
        options = {"manager": self.manager.username, "course_id": str(self.key), "stdout": StringIO()}
        with self.assertRaises(CommandError):
            call_command("sis_bind_course", **options)
        self.authoring_rights.return_value = False
        with self.assertRaises(CommandError):
            call_command("sis_bind_course", confirm=True, **options)
        self.assertFalse(ManagedCourse.objects.filter(course_id=str(self.key)).exists())
        self.authoring_rights.return_value = True
        for _ in range(2):
            call_command("sis_bind_course", confirm=True, **options)
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.assertEqual(course.display_name, "Historical")
        self.assertEqual(course.other_course_settings["existing"], "value")
        self.assertTrue(ManagedCourse.objects.get(course_id=str(self.key)).adopted)
        self.create.assert_not_called()
        self.resume.assert_not_called()

    def test_api_cannot_finish_an_unconfirmed_historical_binding(self):
        ManagedCourse.objects.create(course_id=str(self.key), manager=self.manager, adopted=True)
        self.assertEqual(self.client.post(self.url, self.payload, format="json").status_code, 409)
        self.create.assert_not_called()
        self.resume.assert_not_called()
