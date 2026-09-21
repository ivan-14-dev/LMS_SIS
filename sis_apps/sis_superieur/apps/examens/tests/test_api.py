"""API tests for examens."""

from datetime import timedelta
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from apps.examens.api import IsExamManager, ResultatsExamenViewSet, _ensure_entry_allowed
from django.urls import resolve
from django.utils import timezone
from rest_framework.test import APIRequestFactory


class ExamensAPITestCase(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def test_exam_routes_are_exposed(self):
        self.assertEqual(
            resolve("/api/v1/examens/epreuves/").url_name,
            "epreuve-examen-list",
        )
        self.assertEqual(
            resolve("/api/v1/examens/epreuves/1/historique/").url_name,
            "epreuve-examen-historique",
        )
        self.assertEqual(
            resolve("/api/v1/examens/sessions/1/historique/").url_name,
            "session-examen-historique",
        )
        self.assertEqual(
            resolve("/api/v1/examens/convocations/").url_name,
            "convocation-examen-list",
        )
        self.assertEqual(
            resolve("/api/v1/examens/resultats/").url_name,
            "resultat-examen-list",
        )
        self.assertEqual(
            resolve("/api/v1/examens/resultats/exporter/").url_name,
            "resultat-examen-exporter",
        )

    def test_exam_manager_role_can_access_sensitive_actions(self):
        request = SimpleNamespace(
            method="GET",
            user=SimpleNamespace(
                is_authenticated=True, is_staff=False, role="scolarite"
            ),
        )

        self.assertTrue(IsExamManager().has_permission(request, None))

    def test_student_cannot_access_sensitive_exam_actions(self):
        request = SimpleNamespace(
            method="GET",
            user=SimpleNamespace(
                is_authenticated=True, is_staff=False, role="etudiant"
            ),
        )

        self.assertFalse(IsExamManager().has_permission(request, None))

    def test_default_configuration_resolves_superior_exam_workflow(self):
        from sis_common.academic_configuration import (
            default_academic_configuration,
            resolve_exam_result_workflow,
        )

        workflow = resolve_exam_result_workflow(
            default_academic_configuration(),
            {"scope": "tenant", "context": {"tenant_id": 1}},
            variant="superieur",
        )

        self.assertEqual(workflow["code"], "default_superior_exam_results")

    @patch("apps.examens.api.request_has_business_access", return_value=False)
    def test_student_queryset_only_returns_published_results(self, _business_access):
        request = self.factory.get("/api/v1/examens/resultats/")
        student = SimpleNamespace(is_authenticated=True, is_staff=False, role="etudiant")
        request.user = student
        request.tenant = SimpleNamespace(configuration_academique={})

        class FakeQuerySet:
            def __init__(self):
                self.filters = []

            def select_related(self, *_args):
                return self

            def filter(self, **kwargs):
                self.filters.append(kwargs)
                return self

        view = ResultatsExamenViewSet()
        view.request = request

        queryset = FakeQuerySet()
        with patch("apps.examens.api.ResultatExamen.objects", SimpleNamespace(select_related=lambda *_args: queryset)):
            result = view.get_queryset()

        self.assertIs(result, queryset)
        self.assertEqual(queryset.filters, [{"etudiant__user": student, "statut": "published"}])

    def test_superior_exam_result_submission_allows_active_window(self):
        now = timezone.now()
        epreuve = SimpleNamespace(
            debut_soumission=now - timedelta(hours=1),
            fin_soumission=now + timedelta(hours=1),
            session=SimpleNamespace(
                cloturee=False,
                semestre=SimpleNamespace(
                    cloture=False,
                    annee_universitaire=SimpleNamespace(cloturee=False),
                ),
            ),
        )

        _ensure_entry_allowed(epreuve, "normal", {})
