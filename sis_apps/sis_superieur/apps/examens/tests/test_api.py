"""API tests for examens."""

from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

from apps.examens.api import IsExamManager, ResultatsExamenViewSet, _ensure_entry_allowed
from django.urls import resolve
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIRequestFactory, force_authenticate


class ExamensAPITestCase(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def test_exam_routes_are_exposed(self):
        assert resolve("/api/v1/examens/epreuves/").url_name == "epreuve-examen-list"
        assert resolve("/api/v1/examens/epreuves/1/historique/").url_name == "epreuve-examen-historique"
        assert resolve("/api/v1/examens/sessions/1/historique/").url_name == "session-examen-historique"
        assert resolve("/api/v1/examens/convocations/").url_name == "convocation-examen-list"
        assert resolve("/api/v1/examens/resultats/").url_name == "resultat-examen-list"
        assert resolve("/api/v1/examens/resultats/exporter/").url_name == "resultat-examen-exporter"

    def test_exam_manager_role_can_access_sensitive_actions(self):
        request = SimpleNamespace(
            method="GET",
            user=SimpleNamespace(
                is_authenticated=True,
                is_staff=False,
                is_superuser=False,
                has_perm=lambda permission: False,
                role="scolarite",
            ),
        )

        assert IsExamManager().has_permission(request, None)

    def test_student_cannot_access_sensitive_exam_actions(self):
        request = SimpleNamespace(
            method="GET",
            user=SimpleNamespace(
                is_authenticated=True,
                is_staff=False,
                is_superuser=False,
                has_perm=lambda permission: False,
                role="etudiant",
            ),
        )

        assert not IsExamManager().has_permission(request, None)

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

        assert workflow["code"] == "default_superior_exam_results"

    @patch("apps.examens.api.request_has_business_access", return_value=False)
    def test_student_queryset_only_returns_published_results(self, _business_access):  # noqa: PT019
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

        assert result is queryset
        assert queryset.filters == [{"etudiant__user": student, "statut": "published"}]

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

    @patch("apps.examens.api.record_workflow_event")
    @patch("apps.examens.api._exam_result_workflow", return_value={})
    def test_validated_result_can_be_published_after_entry_deadline(self, workflow_mock, _event):
        now = timezone.now()
        request = SimpleNamespace(
            user=SimpleNamespace(is_staff=True),
            tenant=SimpleNamespace(configuration_academique={}),
        )
        for result_type, session_closed, workflow in (
            ("normal", False, {}),
            ("retake", True, {"allow_retake_after_closure": True}),
        ):
            with self.subTest(result_type=result_type, session_closed=session_closed):
                workflow_mock.return_value = workflow
                epreuve = SimpleNamespace(
                    debut_soumission=now - timedelta(days=2),
                    fin_soumission=now - timedelta(days=1),
                    session=SimpleNamespace(
                        cloturee=session_closed,
                        numero=2 if result_type == "retake" else 1,
                        type="rattrapage" if result_type == "retake" else "normale",
                        semestre=SimpleNamespace(
                            cloture=False,
                            annee_universitaire=SimpleNamespace(cloturee=False),
                        ),
                    ),
                )
                result = SimpleNamespace(
                    epreuve=epreuve,
                    etudiant=SimpleNamespace(user=SimpleNamespace()),
                    statut="validated",
                    type_resultat=result_type,
                    note=Decimal("14"),
                    admis=False,
                    mention="",
                    save=Mock(),
                )
                view = ResultatsExamenViewSet()
                view.get_object = Mock(return_value=result)
                view.get_serializer = Mock(return_value=SimpleNamespace(data={"statut": "published"}))

                # Invoke the API action without its database transaction; the result itself is a stub.
                response = ResultatsExamenViewSet.publier.__wrapped__(view, request, pk=1)

                assert response.status_code == 200
                assert result.statut == "published"
                assert result.note == Decimal("14")
                assert result.admis is True
                assert result.mention == "Bien"
                result.save.assert_called_once()

    @patch("django.db.transaction.Atomic.__exit__", return_value=False)
    @patch("django.db.transaction.Atomic.__enter__")
    @patch("apps.examens.api.record_workflow_event")
    @patch("apps.examens.api._exam_result_workflow", return_value={"allow_retake_after_closure": True})
    def test_closed_normal_session_cannot_publish_result_disguised_as_retake(
        self, _workflow, event, _enter, _exit
    ):
        epreuve = SimpleNamespace(
            fin_soumission=timezone.now() - timedelta(days=1),
            session=SimpleNamespace(
                numero=1,
                type="normale",
                cloturee=True,
                semestre=SimpleNamespace(
                    cloture=False,
                    annee_universitaire=SimpleNamespace(cloturee=False),
                ),
            ),
        )
        result = SimpleNamespace(
            epreuve=epreuve,
            etudiant=SimpleNamespace(user=SimpleNamespace()),
            type_resultat="retake",
            statut="validated",
            note=Decimal("14"),
            save=Mock(),
        )
        request = self.factory.post("/api/v1/examens/resultats/1/publier/")
        force_authenticate(request, user=SimpleNamespace(pk=1, is_authenticated=True, is_staff=True))
        with (
            patch.object(ResultatsExamenViewSet, "get_object", return_value=result),
            patch.object(ResultatsExamenViewSet, "get_serializer", return_value=SimpleNamespace(data={})),
        ):
            response = resolve(request.path).func(request, pk="1")

        assert response.status_code == 400
        assert "workflow" in response.data
        assert result.statut == "validated"
        result.save.assert_not_called()
        event.assert_not_called()

    @patch("django.db.transaction.Atomic.__exit__", return_value=False)
    @patch("django.db.transaction.Atomic.__enter__")
    @patch("apps.examens.api.record_workflow_event")
    @patch("apps.examens.api._exam_result_workflow", return_value={"allow_retake_after_closure": True})
    def test_closed_retake_session_can_publish_validated_result(
        self, _workflow, event, _enter, _exit
    ):
        epreuve = SimpleNamespace(
            fin_soumission=timezone.now() - timedelta(days=1),
            session=SimpleNamespace(
                numero=2,
                type="rattrapage",
                cloturee=True,
                semestre=SimpleNamespace(
                    cloture=False,
                    annee_universitaire=SimpleNamespace(cloturee=False),
                ),
            ),
        )
        result = SimpleNamespace(
            epreuve=epreuve,
            etudiant=SimpleNamespace(user=SimpleNamespace()),
            type_resultat="retake",
            statut="validated",
            note=Decimal("14"),
            save=Mock(),
        )
        request = self.factory.post("/api/v1/examens/resultats/1/publier/")
        force_authenticate(request, user=SimpleNamespace(pk=1, is_authenticated=True, is_staff=True))
        with (
            patch.object(ResultatsExamenViewSet, "get_object", return_value=result),
            patch.object(
                ResultatsExamenViewSet, "get_serializer",
                return_value=SimpleNamespace(data={"statut": "published"}),
            ),
        ):
            response = resolve(request.path).func(request, pk="1")

        assert response.status_code == 200
        assert result.statut == "published"
        result.save.assert_called_once()
        event.assert_called_once()

    @patch("apps.examens.api._exam_result_workflow", return_value={})
    def test_closed_academic_period_still_rejects_publication(self, _workflow):
        request = SimpleNamespace(user=SimpleNamespace(is_staff=True))
        for closed_period, result_type in (
            ("session", "normal"),
            ("semestre", "normal"),
            ("annee", "normal"),
            ("session", "retake"),
        ):
            with self.subTest(closed_period=closed_period, result_type=result_type):
                epreuve = SimpleNamespace(
                    fin_soumission=timezone.now() - timedelta(days=1),
                    session=SimpleNamespace(
                        cloturee=closed_period == "session",
                        numero=1,
                        type="normale",
                        semestre=SimpleNamespace(
                            cloture=closed_period == "semestre",
                            annee_universitaire=SimpleNamespace(cloturee=closed_period == "annee"),
                        ),
                    ),
                )
                result = SimpleNamespace(epreuve=epreuve, type_resultat=result_type, statut="validated")
                view = ResultatsExamenViewSet()
                view.get_object = Mock(return_value=result)

                with self.assertRaisesRegex(ValidationError, "clôturé"):
                    ResultatsExamenViewSet.publier.__wrapped__(view, request, pk=1)

                assert result.statut == "validated"

    def test_closed_session_still_rejects_grade_submission(self):
        epreuve = SimpleNamespace(
            session=SimpleNamespace(
                cloturee=True,
                numero=1,
                type="normale",
                semestre=SimpleNamespace(
                    cloture=False,
                    annee_universitaire=SimpleNamespace(cloturee=False),
                ),
            ),
        )
        result = SimpleNamespace(epreuve=epreuve, type_resultat="normal", statut="draft")
        view = ResultatsExamenViewSet()
        view.get_object = Mock(return_value=result)
        request = SimpleNamespace(user=SimpleNamespace(is_staff=True))

        with patch("apps.examens.api._exam_result_workflow", return_value={}):
            with self.assertRaisesRegex(ValidationError, "clôturé"):
                ResultatsExamenViewSet.soumettre.__wrapped__(view, request, pk=1)

        assert result.statut == "draft"
