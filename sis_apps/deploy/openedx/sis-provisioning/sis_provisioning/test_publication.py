from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import connection
from django.test import TestCase, override_settings
from opaque_keys.edx.keys import CourseKey
from rest_framework.exceptions import PermissionDenied
from rest_framework.test import APIClient

from xmodule.modulestore.exceptions import VersionConflictError

from .models import ManagedCourse, ManagedPublication


@override_settings(ALLOWED_HOSTS=["testserver"], SECURE_SSL_REDIRECT=False)
class PublicationTests(TestCase):
    def setUp(self):
        self.enterContext(patch.dict(connection.settings_dict, ATOMIC_REQUESTS=False))
        self.manager = get_user_model().objects.create_user(
            "publication-service", email="publication-service@example.test"
        )
        self.manager.user_permissions.add(
            Permission.objects.get(content_type__app_label="sis_provisioning", codename="publish_courses")
        )
        self.key = CourseKey.from_string("course-v1:SIS_TEST+publication+test")
        self.binding = ManagedCourse.objects.create(course_id=str(self.key), manager=self.manager, initialized=True)
        self.revision = "1" * 24
        self.course = SimpleNamespace(
            location=self.key.make_usage_key("course", "course"),
            course_version=self.revision,
            other_course_settings={
                "sis_provisioning": {"binding": str(self.binding.ownership_token), "manager": self.manager.pk}
            },
        )
        self.store = MagicMock()
        self.store.get_course.return_value = self.course
        self.store.get_items.return_value = [SimpleNamespace()]
        self.store.publish.return_value = SimpleNamespace(course_version="2" * 24)
        self.enterContext(patch("sis_provisioning.publication_views.modulestore", return_value=self.store))
        self.permission = self.enterContext(patch("sis_provisioning.publication_views._check_xblock_permission"))
        self.client = APIClient()
        self.client.force_authenticate(self.manager)
        self.url = f"/api/sis/v1/courses/{self.key}/publication/"
        self.payload = {
            "operation_id": str(uuid4()),
            "expected_revision": self.revision,
            "confirm": True,
        }

    def post(self, **changes):
        return self.client.post(self.url, {**self.payload, **changes}, format="json")

    def test_exact_reviewed_revision_is_published_once_even_after_later_edits(self):
        preview = self.client.get(self.url)
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.data, {"id": str(self.key), "revision": self.revision})
        response = self.post()
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["published_version"], "2" * 24)
        location, actor = self.store.publish.call_args.args
        self.assertEqual(str(location.course_key.version_guid), self.revision)
        self.assertEqual(actor, self.manager.pk)
        self.course.course_version = "3" * 24
        self.assertEqual(self.post().data, response.data)
        self.store.publish.assert_called_once()
        self.assertEqual(ManagedPublication.objects.filter(course=self.binding).count(), 1)

    def test_stale_revision_and_changed_operation_identity_are_refused(self):
        self.course.course_version = "3" * 24
        self.assertEqual(self.post().status_code, 409)
        self.store.publish.assert_not_called()
        self.assertEqual(self.post(expected_revision="3" * 24).status_code, 409)
        response = self.post(operation_id=str(uuid4()), expected_revision="3" * 24)
        self.assertEqual(response.status_code, 200, response.data)

    def test_revoked_foreign_and_unmarked_courses_cannot_be_published(self):
        self.binding.revoked = True
        self.binding.save(update_fields=["revoked"])
        self.assertEqual(self.post().status_code, 409)
        self.binding.revoked = False
        self.binding.manager = get_user_model().objects.create_user(
            "other-publication-service", email="other-publication-service@example.test"
        )
        self.binding.save(update_fields=["revoked", "manager"])
        self.assertEqual(self.post().status_code, 403)
        self.binding.manager = self.manager
        self.binding.save(update_fields=["manager"])
        self.course.other_course_settings = {}
        self.assertEqual(self.post().status_code, 409)
        self.store.publish.assert_not_called()

    def test_service_permission_and_native_authoring_permission_are_both_required(self):
        self.permission.side_effect = PermissionDenied("Native publication denied")
        self.assertEqual(self.post().status_code, 403)
        self.permission.side_effect = None
        self.manager.user_permissions.clear()
        self.assertEqual(self.post().status_code, 403)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.store.publish.assert_not_called()
        self.assertFalse(ManagedPublication.objects.filter(course=self.binding).exists())

    def test_confirmation_units_and_concurrent_revision_are_checked(self):
        for changes in (
            {"confirm": False},
            {"confirm": "true"},
            {"expected_revision": "invalid"},
            {"start": "2000-01-01"},
        ):
            with self.subTest(changes=changes):
                self.assertEqual(self.post(**changes).status_code, 400)
        self.store.get_items.return_value = []
        self.assertEqual(self.post().status_code, 400)
        self.store.get_items.return_value = [SimpleNamespace()]
        self.store.publish.side_effect = VersionConflictError(self.course.location, "3" * 24)
        self.assertEqual(self.post().status_code, 409)
        self.assertEqual(
            ManagedPublication.objects.get(operation_id=self.payload["operation_id"]).published_version, ""
        )

    def test_interrupted_confirmation_never_publishes_a_newer_unreviewed_draft(self):
        publication = ManagedPublication.objects.create(
            operation_id=self.payload["operation_id"], course=self.binding, revision=self.revision
        )
        with patch.object(ManagedPublication, "save", side_effect=RuntimeError("Confirmation interrupted")):
            with self.assertRaisesMessage(RuntimeError, "Confirmation interrupted"):
                self.post()
        publication.refresh_from_db()
        self.assertEqual(publication.published_version, "")
        self.course.course_version = "3" * 24
        self.assertEqual(self.post().status_code, 409)
        self.store.publish.assert_called_once()
