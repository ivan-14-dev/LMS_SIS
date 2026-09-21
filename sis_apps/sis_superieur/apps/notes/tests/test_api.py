"""API integration-style tests for tenant-driven superior note exports."""

from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from django.urls import resolve
from rest_framework.test import APIRequestFactory

from apps.notes.api import EvaluationsViewSet, MoyennesECUEViewSet, MoyennesUEViewSet


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
            has_perm=lambda permission: permission in {"notes.view_evaluation", "notes.view_moyenneecue", "notes.view_moyenneue"},
        )

    def test_evaluation_export_route_is_registered(self):
        match = resolve("/api/v1/notes/evaluations/exporter/")

        self.assertEqual(match.url_name, "evaluation-exporter")

    def test_evaluation_import_routes_are_registered(self):
        template_match = resolve("/api/v1/notes/evaluations/1/modele_import_notes/")
        import_match = resolve("/api/v1/notes/evaluations/1/importer_notes/")

        self.assertEqual(template_match.url_name, "evaluation-modele-import-notes")
        self.assertEqual(import_match.url_name, "evaluation-importer-notes")

    def test_average_export_routes_are_registered(self):
        ecue_match = resolve("/api/v1/notes/moyennes-ecue/exporter/")
        ue_match = resolve("/api/v1/notes/moyennes-ue/exporter/")

        self.assertEqual(ecue_match.url_name, "moyenne-ecue-exporter")
        self.assertEqual(ue_match.url_name, "moyenne-ue-exporter")

    def test_evaluation_export_uses_tenant_report_configuration(self):
        request = self.factory.post(
            "/api/v1/notes/evaluations/exporter/",
            {
                "report": "evaluations-superieur",
                "filters": {"modalite": "cc"},
            },
            format="json",
        )
        request.user = self.user
        request.tenant = SimpleNamespace(
            configuration_academique={
                "reports": [
                    {
                        "code": "evaluations-superieur",
                        "label": "Évaluations supérieur",
                        "dataset": "evaluations",
                        "fields": ["titre", "modalite"],
                        "allowed_filters": ["modalite"],
                    }
                ]
            }
        )
        queryset = FakeQuerySet([("CC1", "cc")])
        view = EvaluationsViewSet()
        view.request = request
        view.action = "exporter"
        view.get_queryset = lambda: queryset
        view.filter_queryset = lambda qs: qs

        response = view.exporter(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(queryset.filters, [{"modalite": "cc"}])
        self.assertEqual(queryset.selected_fields, ("titre", "modalite"))
        self.assertIn("CC1,cc", response.content.decode())

    @patch("apps.notes.api._import_superior_notes", return_value=(3, 0))
    @patch("apps.notes.api.load_excel_rows", return_value=[{"matricule": "SUP-001", "note": "15", "appreciation": "", "statut": "presente", "__row_number__": 2}])
    def test_superior_note_import_uses_excel_template_rules(self, _load_rows, _import_notes):
        request = self.factory.post("/api/v1/notes/evaluations/1/importer_notes/", {}, format="multipart")
        request.user = self.user
        request.tenant = SimpleNamespace(
            configuration_academique={"import_templates": [{"code": "continuous_assessment_grades"}]}
        )
        request.FILES["file"] = SimpleNamespace(name="notes.xlsx")
        evaluation = SimpleNamespace(
            pk=1,
            modalite="cc",
            semestre=SimpleNamespace(cloture=False, annee_universitaire=SimpleNamespace(cloturee=False)),
        )

        view = EvaluationsViewSet()
        view.request = request
        view.action = "importer_notes"
        view.get_object = lambda: evaluation

        response = view.importer_notes(request, pk=1)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["evaluation_id"], 1)
        self.assertEqual(response.data["notes_creees"], 3)
        self.assertEqual(response.data["notes_modifiees"], 0)

    @patch("apps.notes.api.request_has_business_access", return_value=True)
    @patch("apps.notes.api.filter_queryset_by_scopes", side_effect=lambda qs, *_args, **_kwargs: qs)
    def test_average_exports_use_tenant_report_configuration(self, _scoped_queryset, _business_access):
        ecue_request = self.factory.post(
            "/api/v1/notes/moyennes-ecue/exporter/",
            {
                "report": "averages-ecue",
                "filters": {"valide": True},
            },
            format="json",
        )
        ue_request = self.factory.post(
            "/api/v1/notes/moyennes-ue/exporter/",
            {
                "report": "averages-ue",
                "filters": {"capitalisee": True},
            },
            format="json",
        )
        tenant = SimpleNamespace(
            configuration_academique={
                "reports": [
                    {
                        "code": "averages-ecue",
                        "label": "Moyennes ECUE",
                        "dataset": "averages_ecue",
                        "fields": ["matricule", "moyenne"],
                        "allowed_filters": ["valide"],
                    },
                    {
                        "code": "averages-ue",
                        "label": "Moyennes UE",
                        "dataset": "averages_ue",
                        "fields": ["matricule", "credits_obtenus"],
                        "allowed_filters": ["capitalisee"],
                    },
                ]
            }
        )
        ecue_request.user = self.user
        ecue_request.tenant = tenant
        ue_request.user = self.user
        ue_request.tenant = tenant
        ecue_queryset = FakeQuerySet([("SUP-001", "15.25")])
        ue_queryset = FakeQuerySet([("SUP-001", "30.0")])

        ecue_view = MoyennesECUEViewSet()
        ecue_view.request = ecue_request
        ecue_view.action = "exporter"
        ecue_view.get_queryset = lambda: ecue_queryset
        ecue_view.filter_queryset = lambda qs: qs

        ue_view = MoyennesUEViewSet()
        ue_view.request = ue_request
        ue_view.action = "exporter"
        ue_view.get_queryset = lambda: ue_queryset
        ue_view.filter_queryset = lambda qs: qs

        ecue_response = ecue_view.exporter(ecue_request)
        ue_response = ue_view.exporter(ue_request)

        self.assertEqual(ecue_response.status_code, 200)
        self.assertEqual(ecue_queryset.filters, [{"valide": True}])
        self.assertEqual(ecue_queryset.selected_fields, ("etudiant__matricule", "moyenne"))
        self.assertIn("SUP-001,15.25", ecue_response.content.decode())

        self.assertEqual(ue_response.status_code, 200)
        self.assertEqual(ue_queryset.filters, [{"capitalisee": True}])
        self.assertEqual(ue_queryset.selected_fields, ("etudiant__matricule", "credits_obtenus"))
        self.assertIn("SUP-001,30.0", ue_response.content.decode())
