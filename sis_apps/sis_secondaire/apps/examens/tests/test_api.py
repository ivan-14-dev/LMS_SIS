"""API tests for examens."""

from datetime import timedelta
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

import pytest
from apps.examens.api import (
    IsExamManager,
    IsScolariteOrReadOnly,
    ResultatsExamenViewSet,
    _ensure_entry_allowed,
)
from django.urls import resolve
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIRequestFactory


class ExamensAPITestCase(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def test_exam_routes_are_exposed(self):
        assert resolve("/api/v1/examens/epreuves/").url_name == "epreuve-examen-list"
        assert resolve("/api/v1/examens/epreuves/1/historique/").url_name == "epreuve-examen-historique"
        assert resolve("/api/v1/examens/sessions/1/historique/").url_name == "session-examen-historique"
        assert resolve("/api/v1/examens/resultats/").url_name == "resultat-examen-list"
        assert resolve("/api/v1/examens/resultats/exporter/").url_name == "resultat-examen-exporter"
        assert resolve("/api/v1/examens/resultats/modele_import/").url_name == "resultat-examen-modele-import"

    def test_existing_school_roles_can_manage_exams(self):
        request = SimpleNamespace(
            method="POST",
            user=SimpleNamespace(
                is_authenticated=True,
                is_staff=False,
                is_superuser=False,
                has_perm=lambda permission: False,
                role="vie_scolaire",
            ),
        )

        assert IsScolariteOrReadOnly().has_permission(request, None)
        assert IsExamManager().has_permission(request, None)

    def test_student_cannot_access_sensitive_exam_actions(self):
        request = SimpleNamespace(
            method="GET",
            user=SimpleNamespace(
                is_authenticated=True,
                is_staff=False,
                is_superuser=False,
                has_perm=lambda permission: False,
                role="eleve",
            ),
        )

        assert not IsExamManager().has_permission(request, None)

    @patch("apps.examens.api.IsExamManager.has_permission", return_value=False)
    def test_student_queryset_only_returns_published_results(self, _is_exam_manager):  # noqa: PT019
        request = self.factory.get("/api/v1/examens/resultats/")
        student = SimpleNamespace(
            is_authenticated=True,
            is_staff=False,
            is_superuser=False,
            has_perm=lambda permission: False,
            role="eleve",
        )
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

        assert result is queryset
        assert queryset.filters == [{"eleve__user": student, "statut": "published"}]

    def test_secondary_exam_result_submission_blocks_expired_window(self):
        epreuve = SimpleNamespace(
            debut_soumission=None,
            fin_soumission=timezone.now() - timedelta(minutes=5),
            session=SimpleNamespace(
                cloturee=False,
                annee_scolaire=SimpleNamespace(cloturee=False),
            ),
        )

        with pytest.raises(ValidationError) as context:
            _ensure_entry_allowed(epreuve, "normal", {})

        assert "workflow" in context.value.detail
