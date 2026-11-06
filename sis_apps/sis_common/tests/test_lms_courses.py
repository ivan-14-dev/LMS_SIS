from datetime import date, timedelta
from unittest import TestCase
from unittest.mock import Mock, create_autospec, patch
from uuid import uuid4

import requests
from apps.integration.edx_client import EdxClient
from apps.integration.models import EdxCourseMapping, OutboxEvent
from apps.integration.sync_service import SyncService
from apps.integration.tasks import _publish_outbox_events_for_current_schema
from apps.integration.tests.tenant_test_case import TenantTestCase
from django.apps import apps
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone


class LMSCourseContractTests(TestCase):
    def setUp(self):
        self.client = EdxClient(
            lms_url="https://lms.example.test",
            cms_url="https://studio.example.test",
            oauth_client_id="synthetic-client",
            oauth_client_secret="synthetic-secret",
        )
        self.client._access_token = "synthetic-token"
        self.client._token_expires_at = float("inf")
        self.key = "course-v1:SIS+opaque-course+sis"
        self.course = {"id": self.key, "display_name": "Synthetic Course"}

    def response(self, **changes):
        response = Mock(spec=requests.Response)
        response.status_code = 200
        response.json.return_value = {**self.course, **changes}
        return response

    @patch("sis_common.lms_courses.requests.post")
    def test_creation_uses_the_owned_studio_contract(self, post):
        post.return_value = self.response()
        self.assertEqual(self.client.create_course("SIS", "opaque-course", "sis", "Synthetic Course"), self.course)
        post.assert_called_once_with(
            f"https://studio.example.test/api/sis/v1/courses/{self.key}/",
            json={"display_name": "Synthetic Course"},
            headers=self.client._headers(),
            timeout=30,
            verify=True,
            allow_redirects=False,
        )

    @patch("sis_common.lms_courses.requests.patch")
    @patch("sis_common.lms_courses.requests.get")
    def test_read_and_rename_keep_the_same_identity_and_tls_policy(self, get, update):
        get.return_value = self.response()
        self.assertEqual(self.client.get_course(self.key), self.course)
        update.return_value = self.response(display_name="Renamed")
        self.client.verify_ssl = False
        self.client.update_course(self.key, {"display_name": "Renamed"})
        self.assertFalse(update.call_args.kwargs["verify"])
        self.assertFalse(update.call_args.kwargs["allow_redirects"])
        get.return_value.status_code = 404
        self.assertIsNone(self.client.get_course(self.key))

    @patch("sis_common.lms_courses.requests.post")
    def test_invalid_identity_or_metadata_is_not_sent(self, post):
        for org, name, extra in (
            ("SIS/elsewhere", "Name", None),
            (None, "Name", None),
            ("SIS", "", None),
            ("SIS", "Name", {"start": "2000-01-01"}),
        ):
            with self.subTest(org=org, name=name), self.assertRaises(ValueError):
                self.client.create_course(org, "opaque-course", "sis", name, extra)
        post.assert_not_called()

    @patch("sis_common.lms_courses.requests.post")
    def test_creation_is_limited_to_sis_owned_namespaces(self, post):
        post.return_value = self.response(id="course-v1:SIS-U+opaque-course+sis")
        self.assertEqual(
            self.client.create_course("SIS-U", "opaque-course", "sis", "Synthetic Course")["id"],
            "course-v1:SIS-U+opaque-course+sis",
        )
        post.reset_mock()
        for org, run in (("Other", "sis"), ("SIS", "other"), ("SIS-U", "other")):
            with self.subTest(org=org, run=run), self.assertRaises(ValueError):
                self.client.create_course(org, "opaque-course", run, "Synthetic Course")
        post.assert_not_called()

    @patch("sis_common.lms_courses.requests.post")
    def test_wrong_or_incomplete_confirmation_does_not_create_a_local_success(self, post):
        for changes in ({"id": None}, {"id": "another-course"}, {"display_name": None}, {"display_name": "Other"}):
            post.return_value = self.response(**changes)
            with self.subTest(changes=changes), self.assertRaisesRegex(ValueError, "identité"):
                self.client.create_course("SIS", "opaque-course", "sis", "Synthetic Course")
        post.return_value.status_code = 302
        with self.assertRaisesRegex(ValueError, "provisioning"):
            self.client.create_course("SIS", "opaque-course", "sis", "Synthetic Course")
        post.return_value = self.response()
        post.return_value.raise_for_status.side_effect = requests.HTTPError("403 service denied")
        with self.assertRaises(requests.HTTPError):
            self.client.create_course("SIS", "opaque-course", "sis", "Synthetic Course")

    @patch("sis_common.lms_courses.requests.post")
    @patch("sis_common.lms_courses.requests.get")
    def test_publication_requires_the_reviewed_revision_and_preserves_operation_identity(self, get, post):
        revision = "1" * 24
        operation = str(uuid4())
        get.return_value = self.response(revision=revision)
        self.assertEqual(self.client.get_course_revision(self.key)["revision"], revision)
        self.assertEqual(
            get.call_args.args[0], f"https://studio.example.test/api/sis/v1/courses/{self.key}/publication/"
        )
        post.return_value = self.response(revision=revision, operation_id=operation, published_version="2" * 24)
        result = self.client.publish_course(self.key, expected_revision=revision, operation_id=operation, confirm=True)
        self.assertEqual(result["operation_id"], operation)
        post.assert_called_once_with(
            f"https://studio.example.test/api/sis/v1/courses/{self.key}/publication/",
            json={"expected_revision": revision, "operation_id": operation, "confirm": True},
            headers=self.client._headers(),
            timeout=30,
            verify=True,
            allow_redirects=False,
        )

    @patch("sis_common.lms_courses.requests.post")
    def test_publication_never_sends_an_unconfirmed_or_invalid_revision(self, post):
        payload = {"expected_revision": "1" * 24, "operation_id": str(uuid4()), "confirm": True}
        for changes in (
            {"confirm": False},
            {"confirm": "true"},
            {"expected_revision": "latest"},
            {"operation_id": None},
            {"operation_id": "invalid"},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.client.publish_course(self.key, **{**payload, **changes})
        post.assert_not_called()

    @patch("sis_common.lms_courses.requests.post")
    def test_publication_does_not_accept_a_different_operation_revision_or_course(self, post):
        operation = str(uuid4())
        for changes in (
            {"revision": "3" * 24},
            {"operation_id": str(uuid4())},
            {"published_version": None},
            {"id": "course-v1:SIS+other+sis"},
        ):
            result = {"revision": "1" * 24, "operation_id": operation, "published_version": "2" * 24, **changes}
            post.return_value = self.response(**result)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.client.publish_course(self.key, expected_revision="1" * 24, operation_id=operation, confirm=True)


class LMSCourseIdentityTests(TenantTestCase):
    def setUp(self):
        self.secondary = apps.is_installed("apps.classes")
        if self.secondary:
            year = apps.get_model("etablissement", "AnneeScolaire").objects.create(
                etablissement=self.tenant, libelle="2026-2027", date_debut=date(2026, 9, 1), date_fin=date(2027, 6, 30)
            )
            level = apps.get_model("etablissement", "Niveau").objects.create(
                etablissement=self.tenant, code="6e", libelle="Sixieme"
            )
            self.context = apps.get_model("classes", "Classe").objects.create(
                etablissement=self.tenant, annee_scolaire=year, niveau=level, nom="6e A"
            )
            self.source = apps.get_model("classes", "Matiere").objects.create(
                etablissement=self.tenant, code="MATH", nom="Mathematiques"
            )
            self.lookup = {"matiere": self.source, "classe": self.context}
            self.previous = [("classes", "0006_classe_organisation_unit")]
            self.current = [("classes", "0007_classe_integration_id_matiere_integration_id")]
            self.legacy_values = {"etablissement_id": self.tenant.pk}
        else:
            self.context = apps.get_model("etablissement", "AnneeUniversitaire").objects.create(
                universite=self.tenant, libelle="2026-2027", date_debut=date(2026, 9, 1), date_fin=date(2027, 6, 30)
            )
            semester = apps.get_model("etablissement", "Semestre").objects.create(
                annee_universitaire=self.context,
                numero=1,
                type="impair",
                date_debut=date(2026, 9, 1),
                date_fin=date(2027, 1, 31),
            )
            program = apps.get_model("formations", "Formation").objects.create(
                nom="Informatique", code="INFO", type="licence"
            )
            curriculum = apps.get_model("formations", "MaquetteFormation").objects.create(
                formation=program, annee_universitaire=self.context
            )
            unit = apps.get_model("ue_ecue", "UE").objects.create(
                maquette=curriculum, code="UE1", nom="Programmation", credits_ects=6, semestre=semester
            )
            self.source = apps.get_model("ue_ecue", "ECUE").objects.create(
                ue=unit, code="ECUE1", nom="Algorithmique", credits_ects=3
            )
            self.lookup = {"ecue": self.source}
            self.previous = [("ue_ecue", "0002_alter_ue_type")]
            self.current = [("ue_ecue", "0003_ecue_integration_id")]
            self.legacy_values = {"ue_id": unit.pk, "credits_ects": 3}
        self.remote = create_autospec(EdxClient, instance=True)
        self.remote.create_course.side_effect = self.confirm_creation
        self.remote.update_course.side_effect = lambda key, data: {"id": key, **data}
        self.enterContext(patch("apps.integration.sync_service.get_edx_client", return_value=self.remote))

    @staticmethod
    def confirm_creation(**data):
        return {
            "id": f"course-v1:{data['org']}+{data['number']}+{data['run']}",
            "display_name": data["display_name"],
        }

    def sync(self, name="Synthetic Course", **options):
        return SyncService().sync_course_to_cms(self.source, self.context, name, **options)

    def test_failed_creation_and_source_rename_keep_the_same_remote_identity(self):
        self.remote.create_course.side_effect = requests.ConnectionError("response lost")
        with self.assertRaises(requests.ConnectionError):
            self.sync()
        attempted = self.remote.create_course.call_args.kwargs
        self.assertFalse(EdxCourseMapping.objects.filter(**self.lookup).exists())
        type(self.source).objects.filter(pk=self.source.pk).update(code="NEW", nom="Renamed source")
        self.remote.create_course.side_effect = self.confirm_creation
        self.assertEqual(_publish_outbox_events_for_current_schema(), 1)
        mapping = EdxCourseMapping.objects.get(**self.lookup)
        self.assertEqual(mapping.course_id, self.confirm_creation(**attempted)["id"])
        self.assertEqual(OutboxEvent.objects.get(event_type="course.create").statut, "done")
        renamed = self.sync("Updated Course")
        self.assertEqual(renamed.pk, mapping.pk)
        self.assertEqual(renamed.course_id, mapping.course_id)
        self.assertEqual(renamed.course_name, "Updated Course")

    def test_historical_mapping_is_updated_not_replaced(self):
        mapping = EdxCourseMapping.objects.create(
            **self.lookup, course_id="course-v1:Legacy+Existing+2024", course_name="Historical"
        )
        updated = self.sync("Renamed")
        self.assertEqual(updated.pk, mapping.pk)
        self.assertEqual(updated.course_id, mapping.course_id)
        self.remote.create_course.assert_not_called()
        self.remote.update_course.assert_called_once_with(mapping.course_id, {"display_name": "Renamed"})

    def test_revoked_mapping_is_not_reactivated_by_a_retry(self):
        mapping = self.sync()
        EdxCourseMapping.objects.filter(pk=mapping.pk).update(actif=False)
        self.remote.reset_mock()
        with self.assertRaisesRegex(ValueError, "révoquée"):
            self.sync()
        self.remote.create_course.assert_not_called()
        self.remote.update_course.assert_not_called()
        mapping.refresh_from_db()
        self.assertFalse(mapping.actif)

    def test_older_outbox_event_cannot_overwrite_a_newer_success(self):
        earlier = timezone.now() - timedelta(minutes=2)
        self.remote.create_course.side_effect = requests.ConnectionError("response lost")
        with self.assertRaises(requests.ConnectionError):
            self.sync("Old title", requested_at=earlier)
        self.remote.create_course.side_effect = self.confirm_creation
        mapping = self.sync("Current title", requested_at=earlier + timedelta(minutes=1))
        self.remote.reset_mock()
        self.assertEqual(_publish_outbox_events_for_current_schema(), 1)
        self.remote.create_course.assert_not_called()
        self.remote.update_course.assert_not_called()
        mapping.refresh_from_db()
        self.assertEqual(mapping.course_name, "Current title")

    def test_migration_backfills_distinct_ids_and_preserves_old_binary_inserts(self):
        executor = MigrationExecutor(connection)
        connection.check_constraints()
        executor.migrate(self.previous)
        try:
            historical = executor.loader.project_state(self.previous).apps
            model = historical.get_model(self.source._meta.app_label, self.source._meta.model_name)
            first = model.objects.create(**self.legacy_values, code="OLD1", nom="First legacy course")
            second = model.objects.create(**self.legacy_values, code="OLD2", nom="Second legacy course")
            if self.secondary:
                old_class = historical.get_model("classes", "Classe")
                another_class = old_class.objects.create(
                    etablissement_id=self.tenant.pk,
                    annee_scolaire_id=self.context.annee_scolaire_id,
                    niveau_id=self.context.niveau_id,
                    nom="6e B",
                )
        finally:
            connection.check_constraints()
            MigrationExecutor(connection).migrate(self.current)
        first = type(self.source).objects.get(pk=first.pk)
        second = type(self.source).objects.get(pk=second.pk)
        self.assertNotEqual(first.integration_id, second.integration_id)
        old_insert = model.objects.create(**self.legacy_values, code="OLD3", nom="Old binary insert")
        third = type(self.source).objects.get(pk=old_insert.pk)
        self.assertNotIn(third.integration_id, (first.integration_id, second.integration_id))
        if self.secondary:
            self.context.refresh_from_db()
            another_class = type(self.context).objects.get(pk=another_class.pk)
            self.assertNotEqual(self.context.integration_id, another_class.integration_id)
