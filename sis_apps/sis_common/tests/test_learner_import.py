import csv
from io import BytesIO, StringIO

from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.utilisateurs.models import Utilisateur
from django.apps import apps
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import resolve
from django_tenants.utils import schema_context
from openpyxl import Workbook, load_workbook
from rest_framework.test import APIRequestFactory, force_authenticate

from sis_common.learner_import import BASE_COLUMNS


class StudentsImportContractTests(TenantAPITestCase):
    def setUp(self):
        self.secondary = settings.SIS_VARIANT == "secondaire"
        resource = "eleves" if self.secondary else "etudiants"
        self.url = f"/api/v1/{resource}/"
        self.model = apps.get_model(resource, "Eleve" if self.secondary else "Etudiant")
        self.columns = [*BASE_COLUMNS, *([] if self.secondary else ["matricule", "telephone"])]
        self.row = {
            "username": "student-51",
            "email": "student51@example.test",
            "first_name": "Amina",
            "last_name": "Dupont",
            "date_naissance": "2005-01-01",
            "lieu_naissance": "Paris",
            "sexe": "F",
            "adresse": "1 rue de Test",
            "code_postal": "75000",
            "ville": "Paris",
        }
        if not self.secondary:
            self.row.update(matricule="MAT-51", telephone="+33100000000")
        self.admin = Utilisateur.objects.create_superuser(
            username="student-import-admin",
            email="admin51@example.test",
            password="Institution-test-password-924!",
            role="super_admin",
            etablissement=self.tenant,
        )
        self.client.force_authenticate(self.admin)

    def uploaded(self, row=None, *, format="csv", columns=None):
        columns = columns or self.columns
        if format == "xlsx":
            workbook = Workbook()
            workbook.active.append(columns)
            workbook.active.append([((row or self.row).get(key)) for key in columns])
            stream = BytesIO()
            workbook.save(stream)
            workbook.close()
            return SimpleUploadedFile("students.xlsx", stream.getvalue())
        stream = StringIO()
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerow({key: (row or self.row).get(key) for key in columns})
        return SimpleUploadedFile("students.csv", stream.getvalue().encode("utf-8"))

    def test_schema_templates_and_preview_support_csv_and_xlsx_without_writes(self):
        schema_response = self.client.get(f"{self.url}importer/")
        assert schema_response.status_code == 200, schema_response.data
        schema = schema_response.data
        assert schema["schema_id"] == f"sis.students.{'secondaire' if self.secondary else 'superieur'}"
        assert schema["schema_version"] == 1
        assert schema["identity_field"] == "username"
        assert schema["formats"] == ["csv", "xlsx"]
        assert [field["id"] for field in schema["columns"]] == self.columns
        required = {field["id"] for field in schema["columns"] if field["required"]}
        assert schema["required_fields"] == [column for column in self.columns if column in required]
        assert {"username", "email", "first_name", "last_name", "date_naissance", "lieu_naissance", "sexe"} <= required
        if not self.secondary:
            assert {"matricule", "telephone", "adresse", "code_postal", "ville"} <= required

        csv_template = self.client.get(f"{self.url}modele-import/", {"type_fichier": "csv"})
        xlsx_template = self.client.get(f"{self.url}modele-import/")
        for template in (csv_template, xlsx_template):
            assert template.status_code == 200
            assert template["X-Import-Schema-Id"] == schema["schema_id"]
            assert template["X-Import-Schema-Version"] == "1"
        assert next(csv.reader(StringIO(csv_template.content.decode("utf-8")))) == self.columns
        workbook = load_workbook(BytesIO(xlsx_template.content), read_only=True)
        try:
            assert list(next(workbook.active.values)) == self.columns
        finally:
            workbook.close()

        for format in ("csv", "xlsx"):
            preview = self.client.post(
                f"{self.url}importer/",
                {
                    "file": self.uploaded(format=format),
                    "schema_id": schema["schema_id"],
                    "schema_version": schema["schema_version"],
                },
            )
            assert preview.status_code == 200, preview.data
            assert preview.data["schema_id"] == schema["schema_id"]
            assert preview.data["schema_version"] == schema["schema_version"]
            assert preview.data["to_create"] == 1
            assert preview.data["errors"] == []
            assert preview.data["rows"] == [{"line": 2, "id": self.row["username"], "status": "create"}]
            assert preview.data["created"] == 0
            assert not self.model.objects.exists()
            assert not Utilisateur.objects.filter(username=self.row["username"]).exists()
            if format == "csv":
                csv_digest = preview.data["digest"]

        confirmed = self.client.post(
            f"{self.url}importer/",
            {"file": self.uploaded(), "schema_version": 1, "apply": "true", "digest": csv_digest},
        )
        assert confirmed.status_code == 200, confirmed.data
        assert confirmed.data["created"] == 1
        learner = self.model.objects.get(user__username=self.row["username"])
        assert learner.user.etablissement_id == self.tenant.pk
        assert getattr(learner, "etablissement_id" if self.secondary else "universite_id") == self.tenant.pk

    def test_corrupt_files_and_required_fields_do_not_write(self):
        wrong_headers = self.client.post(
            f"{self.url}importer/",
            {"file": self.uploaded(columns=self.columns[:-1])},
        )
        assert wrong_headers.status_code == 400
        assert "columns" in wrong_headers.data
        bad_workbook = self.client.post(
            f"{self.url}importer/",
            {"file": SimpleUploadedFile("students.xlsx", b"not a workbook")},
        )
        assert bad_workbook.status_code == 400
        assert "file" in bad_workbook.data
        wrong_version = self.client.post(
            f"{self.url}importer/",
            {"file": self.uploaded(), "schema_version": 2},
        )
        assert wrong_version.status_code == 400
        assert "schema_version" in wrong_version.data
        wrong_id = self.client.post(
            f"{self.url}importer/",
            {"file": self.uploaded(), "schema_id": "sis.students.unknown"},
        )
        assert wrong_id.status_code == 400
        assert "schema_id" in wrong_id.data

        unconfirmed = self.client.post(
            f"{self.url}importer/",
            {"file": self.uploaded(), "apply": "true", "digest": "incorrect"},
        )
        assert unconfirmed.status_code == 400
        assert not self.model.objects.exists()

        preview = self.client.post(
            f"{self.url}importer/",
            {"file": self.uploaded({**self.row, "email": ""}), "schema_version": 1},
        )
        assert preview.status_code == 200, preview.data
        assert preview.data["rows"] == [{"line": 2, "id": self.row["username"], "status": "error"}]
        assert preview.data["errors"][0]["line"] == 2
        assert "email" in preview.data["errors"][0]["errors"]
        confirmed = self.client.post(
            f"{self.url}importer/",
            {
                "file": self.uploaded({**self.row, "email": ""}),
                "schema_version": 1,
                "apply": "true",
                "digest": preview.data["digest"],
            },
        )
        assert confirmed.status_code == 400
        assert not self.model.objects.exists()
        assert not Utilisateur.objects.filter(username=self.row["username"]).exists()

    def test_foreign_tenant_identity_is_not_skipped_or_imported(self):
        foreign = type(self.tenant)(schema_name="foreign_students_import")
        self.setup_tenant(foreign)
        foreign.auto_create_schema = False
        with schema_context("public"):
            foreign.save()
        Utilisateur.objects.create_user(
            username=self.row["username"],
            email="foreign@example.test",
            etablissement=foreign,
        )
        preview = self.client.post(f"{self.url}importer/", {"file": self.uploaded()})
        assert preview.status_code == 200, preview.data
        assert preview.data["to_create"] == 0
        assert preview.data["skipped"] == 0
        assert preview.data["rows"] == [{"line": 2, "id": self.row["username"], "status": "error"}]
        assert preview.data["errors"][0]["line"] == 2
        assert "username" in preview.data["errors"][0]["errors"]

        request = APIRequestFactory().post(
            f"{self.url}importer/",
            {"file": self.uploaded(), "apply": "true", "digest": preview.data["digest"]},
            format="multipart",
        )
        request.tenant = foreign
        force_authenticate(request, user=self.admin)
        cross_tenant = resolve(f"{self.url}importer/").func(request)
        assert cross_tenant.status_code == 400
        assert "file" in cross_tenant.data

        confirmed = self.client.post(
            f"{self.url}importer/",
            {"file": self.uploaded(), "apply": "true", "digest": preview.data["digest"]},
        )
        assert confirmed.status_code == 400
        assert not self.model.objects.exists()
        assert Utilisateur.objects.filter(username=self.row["username"]).count() == 1
