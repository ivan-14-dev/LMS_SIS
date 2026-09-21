"""API tests for examens."""

from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from apps.examens.api import (
    IsExamManager,
    IsScolariteOrReadOnly,
    ResultatsExamenViewSet,
)
from django.urls import resolve
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
            resolve("/api/v1/examens/resultats/").url_name,
            "resultat-examen-list",
        )
        self.assertEqual(
            resolve("/api/v1/examens/resultats/exporter/").url_name,
            "resultat-examen-exporter",
        )
        self.assertEqual(
            resolve("/api/v1/examens/resultats/modele_import/").url_name,
            "resultat-examen-modele-import",
        )

    def test_existing_school_roles_can_manage_exams(self):
        request = SimpleNamespace(
            method="POST",
            user=SimpleNamespace(
                is_authenticated=True, is_staff=False, role="vie_scolaire"
            ),
        )

        self.assertTrue(IsScolariteOrReadOnly().has_permission(request, None))
        self.assertTrue(IsExamManager().has_permission(request, None))

    def test_student_cannot_access_sensitive_exam_actions(self):
        request = SimpleNamespace(
            method="GET",
            user=SimpleNamespace(is_authenticated=True, is_staff=False, role="eleve"),
        )

        self.assertFalse(IsExamManager().has_permission(request, None))

    @patch("apps.examens.api.IsExamManager.has_permission", return_value=False)
    def test_student_queryset_only_returns_published_results(self, _is_exam_manager):
        request = self.factory.get("/api/v1/examens/resultats/")
        student = SimpleNamespace(is_authenticated=True, is_staff=False, role="eleve")
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
        self.assertEqual(queryset.filters, [{"eleve__user": student, "statut": "published"}])
