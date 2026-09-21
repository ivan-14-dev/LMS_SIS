"""API integration-style tests for tenant-driven note exports."""

from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from django.urls import resolve
from rest_framework.test import APIRequestFactory

from apps.notes.api import BulletinsViewSet, EvaluationsViewSet, NotesViewSet


class FakeQuerySet:
    def __init__(self, rows):
        self.rows = rows
        self.filters = []
        self.selected_fields = ()

    def filter(self, **kwargs):
        self.filters.append(kwargs)
        return self

    def values_list(self, *fields):
        self.selected_fields = fields
        return self

    def distinct(self):
        return self.rows


class NotesAPITestCase(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = SimpleNamespace(
            is_authenticated=True,
            is_superuser=False,
            has_perm=lambda permission: permission == "notes.view_note",
        )

    def test_note_export_route_is_registered(self):
        match = resolve("/api/v1/notes/notes/exporter/")

        self.assertEqual(match.url_name, "note-exporter")

    def test_evaluation_import_routes_are_registered(self):
        template_match = resolve("/api/v1/notes/evaluations/1/modele_import_notes/")
        import_match = resolve("/api/v1/notes/evaluations/1/importer_notes/")
        history_match = resolve("/api/v1/notes/evaluations/1/historique/")

        self.assertEqual(template_match.url_name, "evaluation-modele-import-notes")
        self.assertEqual(import_match.url_name, "evaluation-importer-notes")
        self.assertEqual(history_match.url_name, "evaluation-historique")

    def test_bulletin_export_route_is_registered(self):
        match = resolve("/api/v1/notes/bulletins/exporter/")

        self.assertEqual(match.url_name, "bulletin-exporter")

    def test_note_export_uses_tenant_report_configuration(self):
        request = self.factory.post(
            "/api/v1/notes/notes/exporter/",
            {
                "report": "notes-secondary",
                "filters": {"classe": 9},
            },
            format="json",
        )
        request.user = self.user
        request.tenant = SimpleNamespace(
            configuration_academique={
                "reports": [
                    {
                        "code": "notes-secondary",
                        "label": "Notes secondaire",
                        "dataset": "notes",
                        "fields": ["matricule", "note"],
                        "allowed_filters": ["classe"],
                    }
                ]
            }
        )
        queryset = FakeQuerySet([("MAT-001", "14.5")])
        view = NotesViewSet()
        view.request = request
        view.action = "exporter"
        view.get_queryset = lambda: queryset
        view.filter_queryset = lambda qs: qs

        response = view.exporter(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(queryset.filters, [{"evaluation__classe_id": 9}])
        self.assertEqual(queryset.selected_fields, ("eleve__matricule", "valeur"))
        self.assertIn("MAT-001,14.5", response.content.decode())

    @patch("apps.notes.api._import_secondary_notes", return_value=(2, 1))
    @patch("apps.notes.api.load_excel_rows", return_value=[{"matricule": "MAT-001", "note": "14", "appreciation": "", "statut": "presente", "__row_number__": 2}])
    def test_secondary_note_import_uses_excel_template_rules(self, _load_rows, _import_notes):
        request = self.factory.post("/api/v1/notes/evaluations/1/importer_notes/", {}, format="multipart")
        request.user = self.user
        request.tenant = SimpleNamespace(
            configuration_academique={"import_templates": [{"code": "continuous_assessment_grades"}]}
        )
        request.FILES["file"] = SimpleNamespace(name="notes.xlsx")
        evaluation = SimpleNamespace(pk=1, type="ds", classe=SimpleNamespace(annee_scolaire=SimpleNamespace(cloturee=False)), periode=SimpleNamespace(cloturee=False))

        view = EvaluationsViewSet()
        view.request = request
        view.action = "importer_notes"
        view.get_object = lambda: evaluation

        response = view.importer_notes(request, pk=1)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["evaluation_id"], 1)
        self.assertEqual(response.data["notes_creees"], 2)
        self.assertEqual(response.data["notes_modifiees"], 1)

    @patch("apps.notes.api.request_has_business_access", return_value=True)
    @patch("apps.notes.api.filter_queryset_by_scopes", side_effect=lambda qs, *_args, **_kwargs: qs)
    def test_bulletin_export_uses_tenant_report_configuration(self, _scoped_queryset, _business_access):
        request = self.factory.post(
            "/api/v1/notes/bulletins/exporter/",
            {
                "report": "bulletins-secondary",
                "filters": {"publie": True},
            },
            format="json",
        )
        request.user = self.user
        request.tenant = SimpleNamespace(
            configuration_academique={
                "reports": [
                    {
                        "code": "bulletins-secondary",
                        "label": "Bulletins secondaire",
                        "dataset": "bulletins",
                        "fields": ["matricule", "decision"],
                        "allowed_filters": ["publie"],
                    }
                ]
            },
            id=1,
        )
        queryset = FakeQuerySet([("MAT-002", "passage")])
        view = BulletinsViewSet()
        view.request = request
        view.action = "exporter"
        view.get_queryset = lambda: queryset
        view.filter_queryset = lambda qs: qs

        response = view.exporter(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(queryset.filters, [{"publie": True}])
        self.assertEqual(queryset.selected_fields, ("eleve__matricule", "decision"))
        self.assertIn("MAT-002,passage", response.content.decode())
