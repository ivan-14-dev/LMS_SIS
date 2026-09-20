"""API tests for examens."""

from types import SimpleNamespace
from unittest import TestCase

from apps.examens.api import IsExamManager, IsScolariteOrReadOnly
from django.urls import resolve


class ExamensAPITestCase(TestCase):
    def test_exam_routes_are_exposed(self):
        self.assertEqual(
            resolve("/api/v1/examens/epreuves/").url_name,
            "epreuve-examen-list",
        )
        self.assertEqual(
            resolve("/api/v1/examens/resultats/").url_name,
            "resultat-examen-list",
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
