import csv
from datetime import datetime
from io import BytesIO, StringIO

import pyotp
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.utilisateurs.models import Utilisateur
from django.apps import apps
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django_tenants.utils import schema_context
from openpyxl import Workbook
from rest_framework.test import APIClient

from sis_common.learner_import import BASE_COLUMNS
from sis_common.mfa import generate_secret
from sis_common.session_security import revoke_all_sessions

PASSWORD = "Institution-test-password-924!"


class InstitutionWorkflowTest(TenantAPITestCase):
    def setUp(self):
        self.secondary = settings.SIS_VARIANT == "secondaire"
        self.resource = "eleves" if self.secondary else "etudiants"
        self.url = f"/api/v1/{self.resource}/"
        self.model = apps.get_model(self.resource, "Eleve" if self.secondary else "Etudiant")
        self.admin = Utilisateur.objects.create_superuser(
            username="institution-admin",
            email="admin@example.test",
            role="super_admin",
            password=PASSWORD,
            etablissement=self.tenant,
        )
        self.client.force_authenticate(self.admin)
        self.row = {
            "username": "learner-one",
            "email": "learner@example.test",
            "first_name": "Test",
            "last_name": "Learner",
            "date_naissance": "2005-01-01",
            "lieu_naissance": "Paris",
            "sexe": "F",
            "adresse": "1 Test",
            "code_postal": "75000",
            "ville": "Paris",
        }
        if not self.secondary:
            self.row.update(matricule="IMPORT-001", telephone="+33100000000")

    def uploaded(self, rows):
        output = StringIO()
        columns = [
            *BASE_COLUMNS,
            *([] if self.secondary else ["matricule", "telephone"]),
        ]
        writer = csv.DictWriter(output, columns)
        writer.writeheader()
        writer.writerows(rows)
        return SimpleUploadedFile("learners.csv", output.getvalue().encode(), content_type="text/csv")

    def test_real_creation_binds_user_and_learner_to_host_tenant(self):
        response = self.client.post(self.url, {**self.row, "password": PASSWORD}, format="json")
        assert response.status_code == 201, response.data
        learner = self.model.objects.get(user__username=self.row["username"])
        assert learner.user.etablissement_id == self.tenant.pk
        assert getattr(learner, "etablissement_id" if self.secondary else "universite_id") == self.tenant.pk
        duplicate = self.client.post(self.url, {**self.row, "password": PASSWORD}, format="json")
        assert duplicate.status_code == 400
        assert self.model.objects.count() == 1

    def test_xlsx_birth_date_cells_can_be_previewed_and_imported(self):
        workbook = Workbook()
        workbook.active.append(list(self.row))
        workbook.active.append(
            [datetime(2005, 1, 1) if name == "date_naissance" else value for name, value in self.row.items()]
        )
        stream = BytesIO()
        workbook.save(stream)
        workbook.close()

        def uploaded():
            return SimpleUploadedFile("learners.xlsx", stream.getvalue())

        preview = self.client.post(f"{self.url}importer/", {"file": uploaded()})
        assert preview.status_code == 200, preview.data
        assert not preview.data["errors"], preview.data
        result = self.client.post(
            f"{self.url}importer/",
            {"file": uploaded(), "apply": "true", "digest": preview.data["digest"]},
        )
        assert result.status_code == 200, result.data
        assert result.data["created"] == 1
        assert self.model.objects.get().date_naissance.isoformat() == "2005-01-01"

    def test_preview_does_not_write_and_reimport_is_idempotent(self):
        response = self.client.post(f"{self.url}importer/", {"file": self.uploaded([self.row])})
        assert response.status_code == 200, response.data
        assert not response.data["errors"], response.data
        assert self.model.objects.count() == 0
        digest = response.data["digest"]
        for expected_created in (1, 0):
            response = self.client.post(
                f"{self.url}importer/",
                {
                    "file": self.uploaded([self.row]),
                    "apply": "true",
                    "digest": digest,
                },
            )
            assert response.status_code == 200, response.data
            assert response.data["created"] == expected_created
        learner = self.model.objects.get()
        assert learner.user.etablissement_id == self.tenant.pk
        assert not learner.user.has_usable_password()

    def test_import_rejects_duplicate_rows_without_partial_writes(self):
        rows = [self.row, self.row]
        response = self.client.post(f"{self.url}importer/", {"file": self.uploaded(rows)})
        assert response.status_code == 200, response.data
        assert response.data["errors"][0]["line"] == 3
        response = self.client.post(
            f"{self.url}importer/",
            {
                "file": self.uploaded(rows),
                "apply": "true",
                "digest": response.data["digest"],
            },
        )
        assert response.status_code == 400, response.data
        assert self.model.objects.count() == 0
        assert not Utilisateur.objects.filter(username=self.row["username"]).exists()

    def test_learner_without_profile_cannot_list_other_learners(self):
        response = self.client.post(self.url, {**self.row, "password": PASSWORD}, format="json")
        assert response.status_code == 201, response.data
        learner = Utilisateur.objects.create_user(
            "missing-profile",
            role="eleve" if self.secondary else "etudiant",
            etablissement=self.tenant,
        )
        self.client.force_authenticate(learner)
        response = self.client.get(self.url)
        assert response.status_code == 200, response.data
        assert response.data["count"] == 0
        response = self.client.post(f"{self.url}importer/", {"file": self.uploaded([self.row])})
        assert response.status_code == 403

    def test_server_pagination_and_search_reach_later_users(self):
        for index in range(61):
            Utilisateur.objects.create_user(
                f"page-{index:03d}",
                first_name=f"Name{index:03d}",
                etablissement=self.tenant,
            )
        url = "/api/v1/utilisateurs/comptes/"
        response = self.client.get(url, {"page": 2, "page_size": 50})
        assert response.status_code == 200, response.data
        assert response.data["count"] == 62
        assert len(response.data["results"]) == 12
        response = self.client.get(url, {"search": "Name060"})
        assert response.status_code == 200, response.data
        assert [row["username"] for row in response.data["results"]] == ["page-060"]

    def test_academic_dates_duplicates_and_closed_years_are_rejected(self):
        url = "/api/v1/etablissement/annees/"
        row = {
            "libelle": "2026-2027",
            "date_debut": "2026-09-01",
            "date_fin": "2027-07-01",
        }
        response = self.client.post(url, {**row, "date_fin": "2025-01-01"}, format="json")
        assert response.status_code == 400, response.data
        response = self.client.post(url, row, format="json")
        assert response.status_code == 201, response.data
        identifier = response.data["id"]
        response = self.client.post(url, row, format="json")
        assert response.status_code == 400, response.data
        assert self.client.post(f"{url}{identifier}/cloturer/").status_code == 200
        response = self.client.post(f"{url}{identifier}/activer/")
        assert response.status_code == 400, response.data
        response = self.client.patch(f"{url}{identifier}/", {"date_fin": "2027-08-01"}, format="json")
        assert response.status_code == 400, response.data

    def test_related_objects_from_another_institution_are_rejected(self):
        foreign = type(self.tenant)(schema_name="foreign_institution")
        self.setup_tenant(foreign)
        foreign.auto_create_schema = False
        with schema_context("public"):
            foreign.save()
        if self.secondary:
            year_model = apps.get_model("etablissement", "AnneeScolaire")
            year = year_model.objects.create(
                etablissement=foreign,
                libelle="Foreign",
                date_debut="2026-09-01",
                date_fin="2027-07-01",
            )
            level = apps.get_model("etablissement", "Niveau").objects.create(
                etablissement=self.tenant, code="6e", libelle="Sixieme"
            )
            response = self.client.post(
                "/api/v1/classes/classes/",
                {"nom": "6A", "niveau": level.pk, "annee_scolaire": year.pk},
                format="json",
            )
        else:
            foreign_user = Utilisateur.objects.create_user("foreign-dean", etablissement=foreign)
            response = self.client.post(
                "/api/v1/structure/facultes/",
                {
                    "code": "F1",
                    "nom": "Faculty",
                    "date_creation": "2026-01-01",
                    "doyen": foreign_user.pk,
                },
                format="json",
            )
        assert response.status_code == 400, response.data

    def test_corrected_resource_contracts_support_forms_and_lists(self):
        resources = (
            [
                "bulletins/appreciations",
                "cantine/inscriptions-cantine",
                "transport/inscriptions-transport",
                "infirmerie/dossiers-medicaux",
                "infirmerie/visites-infirmerie",
                "internat/occupants-chambres",
                "clubs/membres-clubs",
                "discipline/incidents",
                "discipline/conseils-discipline",
            ]
            if self.secondary
            else ["diplomes/catalogue", "jurys/decisions-globales", "maquettes"]
        )
        for resource in resources:
            with self.subTest(resource=resource):
                url = f"/api/v1/{resource}/"
                response = self.client.options(url)
                assert response.status_code == 200, response.data
                response = self.client.get(url)
                assert response.status_code == 200, response.data

    @override_settings(
        CACHES={
            "default": {
                "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                "LOCATION": "institution-browser-session-contract",
            }
        }
    )
    def test_browser_session_requires_csrf_and_mfa_and_can_be_revoked(self):
        client = APIClient(enforce_csrf_checks=True)
        client.defaults["SERVER_NAME"] = self.get_test_tenant_domain()
        url = "/api/v1/auth/session/"
        credentials = {"username": self.admin.username, "password": PASSWORD}
        assert client.post(url, credentials, format="json").status_code == 403
        token = client.get("/csrf/api/v1/token").json()["csrfToken"]
        self.admin.mfa_secret = generate_secret()
        self.admin.mfa_active = True
        self.admin.save()
        response = client.post(url, credentials, format="json", HTTP_X_CSRFTOKEN=token)
        assert response.status_code == 401, response.data
        response = client.post(
            url,
            {**credentials, "code": pyotp.TOTP(self.admin.mfa_secret).now()},
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )
        assert response.status_code == 200, response.data
        assert client.get(url).data["authenticated"]
        revoke_all_sessions(self.admin)
        assert not client.get(url).data["authenticated"]
