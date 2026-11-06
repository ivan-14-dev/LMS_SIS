"""API tests for evaluations."""

from datetime import timedelta

from apps.etablissement.models import Etablissement
from apps.utilisateurs.models import Utilisateur
from django.test import SimpleTestCase, override_settings
from django.urls import resolve
from django_tenants.utils import schema_context
from sis_common.tests.test_grade_entry import GradeEntryFixture as _GradeEntryFixture


class EvaluationsAPITestCase(SimpleTestCase):
    def test_evaluation_routes_are_registered(self):
        list_match = resolve("/api/v1/evaluations/")
        detail_match = resolve("/api/v1/evaluations/1/")
        notes_match = resolve("/api/v1/evaluations/1/notes/")
        export_match = resolve("/api/v1/evaluations/exporter/")

        assert list_match.url_name == "evaluation-list"
        assert detail_match.url_name == "evaluation-detail"
        assert notes_match.url_name == "evaluation-notes"
        assert export_match.url_name == "evaluation-exporter"


@override_settings(SECURE_SSL_REDIRECT=False)
class EvaluationDateAPITestCase(_GradeEntryFixture):
    def test_create_rejects_date_outside_period(self):
        for route in ("/api/v1/evaluations/", "/api/v1/notes/evaluations/"):
            with self.subTest(route=route):
                response = self.client.post(
                    route,
                    {**self.payload, "date": (self.period.date_debut - timedelta(days=1)).isoformat()},
                    format="json",
                )
                assert response.status_code == 400, response.data
                assert "date" in response.data

    def test_patch_rejects_date_outside_period_without_changing_evaluation(self):
        for route in ("/api/v1/evaluations/", "/api/v1/notes/evaluations/"):
            with self.subTest(route=route):
                response = self.client.patch(
                    f"{route}{self.evaluation.pk}/",
                    {"date": (self.period.date_fin + timedelta(days=1)).isoformat()},
                    format="json",
                )
                assert response.status_code == 400, response.data
                assert "date" in response.data
                self.evaluation.refresh_from_db()
                assert self.evaluation.date == self.today

    def test_period_boundary_dates_are_accepted(self):
        url = f"/api/v1/evaluations/{self.evaluation.pk}/"
        for date in (self.period.date_debut, self.period.date_fin):
            with self.subTest(date=date):
                response = self.client.patch(url, {"date": date.isoformat()}, format="json")
                assert response.status_code == 200, response.data
                self.evaluation.refresh_from_db()
                assert self.evaluation.date == date

    def test_foreign_superuser_cannot_read_or_change_current_tenant_evaluations(self):
        foreign = Etablissement(schema_name="foreign_evaluations")
        self.setup_tenant(foreign)
        foreign.auto_create_schema = False
        with schema_context("public"):
            foreign.save()
        outsider = Utilisateur.objects.create_superuser(
            "foreign-evaluations-admin", role="super_admin", etablissement=foreign
        )
        self.client.force_authenticate(outsider)
        for list_url in ("/api/v1/evaluations/", "/api/v1/notes/evaluations/"):
            with self.subTest(route=list_url):
                detail_url = f"{list_url}{self.evaluation.pk}/"
                assert self.client.get(list_url).status_code == 403
                assert self.client.get(detail_url).status_code == 403
                assert self.client.patch(
                    detail_url, {"titre": "Modifié par un tiers"}, format="json"
                ).status_code == 403
                self.evaluation.refresh_from_db()
                assert self.evaluation.titre == self.payload["titre"]

    def test_current_tenant_superuser_can_read_and_change_evaluation(self):
        for list_url in ("/api/v1/evaluations/", "/api/v1/notes/evaluations/"):
            with self.subTest(route=list_url):
                detail_url = f"{list_url}{self.evaluation.pk}/"
                assert self.client.get(list_url).status_code == 200
                assert self.client.get(detail_url).status_code == 200
                response = self.client.patch(detail_url, {"titre": "Contrôle actualisé"}, format="json")
                assert response.status_code == 200, response.data
                self.evaluation.refresh_from_db()
                assert self.evaluation.titre == "Contrôle actualisé"
