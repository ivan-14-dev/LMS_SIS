"""API tests for examens."""

from types import SimpleNamespace
from unittest import TestCase

from apps.examens.api import IsExamManager
from django.urls import resolve


class ExamensAPITestCase(TestCase):
    def test_exam_routes_are_exposed(self):
        self.assertEqual(
            resolve("/api/v1/examens/epreuves/").url_name,
            "epreuve-examen-list",
        )
        self.assertEqual(
            resolve("/api/v1/examens/convocations/").url_name,
            "convocation-examen-list",
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
