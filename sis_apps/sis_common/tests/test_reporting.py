import csv
from io import BytesIO, StringIO

import pytest
from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError

from sis_common.reporting import configured_report, export_queryset


class FakeUser:
    is_superuser = False

    def __init__(self, permissions=()):
        self.permissions = set(permissions)

    def has_perm(self, permission):
        return permission in self.permissions


class ReportingTests(SimpleTestCase):
    def test_configured_note_export_keeps_text_without_executable_cells(self):
        for export_format in ("csv", "xlsx"):
            with self.subTest(format=export_format):
                self._check_configured_note_export(export_format)

    def _check_configured_note_export(self, export_format):
        class FakeQuerySet:
            def filter(self, **_kwargs):
                return self

            def values_list(self, *_fields):
                return self

            def distinct(self):
                return [(" \t=1+1", 14.5), ("Normal note", 12.5)]

        report = {
            "code": "notes-secondary",
            "label": "=1+1",
            "dataset": "notes",
            "fields": ["appreciation", "note"],
            "allowed_filters": [],
            "formats": ["csv", "xlsx"],
            "required_permissions": ["notes.view_note"],
        }
        request = type(
            "Request",
            (),
            {
                "data": {"format": export_format},
                "user": FakeUser(["notes.view_note"]),
                "tenant": type(
                    "Tenant",
                    (),
                    {"nom": "+1+1", "configuration_academique": {"reports": [report]}},
                )(),
            },
        )()

        selected = configured_report(request, "notes-secondary", allowed_datasets={"notes"})
        response = export_queryset(
            request,
            FakeQuerySet(),
            selected,
            {"appreciation": ("Appréciation", "appreciation"), "note": ("Note", "valeur")},
            {},
            {},
        )

        if export_format == "csv":
            records = list(csv.reader(StringIO(response.content.decode("utf-8"))))
            assert records[0] == ["Établissement", "'+1+1"]
            assert ["Rapport", "'=1+1"] in records
            assert records[-2] == ["' \t=1+1", "14.5"]
            assert records[-1] == ["Normal note", "12.5"]
        else:
            from openpyxl import load_workbook

            sheet = load_workbook(BytesIO(response.content)).active
            assert sheet["B1"].value == "+1+1"
            assert sheet["B1"].data_type == "s"
            report_cell = next(row[1] for row in sheet if row[0].value == "Rapport")
            assert report_cell.value == "=1+1"
            assert report_cell.data_type == "s"
            rows = list(sheet.rows)
            assert rows[-2][0].value == " \t=1+1"
            assert rows[-2][0].data_type == "s"
            assert rows[-2][1].value == 14.5
            assert rows[-2][1].data_type == "n"
            assert rows[-1][0].value == "Normal note"

    def test_configured_report_rejects_wrong_dataset(self):
        request = type(
            "Request",
            (),
            {
                "user": FakeUser(["paiements.view_paiement"]),
                "tenant": type(
                    "Tenant",
                    (),
                    {
                        "configuration_academique": {
                            "reports": [
                                {
                                    "code": "payments",
                                    "label": "Paiements",
                                    "dataset": "financial_payments",
                                    "fields": ["numero"],
                                    "allowed_filters": [],
                                }
                            ]
                        }
                    },
                )(),
            },
        )()

        with pytest.raises(ValidationError):
            configured_report(request, "payments", allowed_datasets={"notes"})

    def test_configured_report_checks_required_permissions(self):
        request = type(
            "Request",
            (),
            {
                "user": FakeUser(),
                "tenant": type(
                    "Tenant",
                    (),
                    {
                        "configuration_academique": {
                            "reports": [
                                {
                                    "code": "payments",
                                    "label": "Paiements",
                                    "dataset": "financial_payments",
                                    "fields": ["numero"],
                                    "allowed_filters": [],
                                    "required_permissions": ["paiements.view_paiement"],
                                }
                            ]
                        }
                    },
                )(),
            },
        )()

        with pytest.raises(ValidationError):
            configured_report(request, "payments", allowed_datasets={"financial_payments"})

    def test_export_queryset_supports_metadata_rich_csv(self):
        class FakeQuerySet:
            def __init__(self):
                self.filters = []

            def filter(self, **kwargs):
                self.filters.append(kwargs)
                return self

            def values_list(self, *_fields):
                return self

            def distinct(self):
                return [("MAT-001", "14.5")]

        request = type(
            "Request",
            (),
            {
                "data": {"format": "csv"},
                "user": FakeUser(),
                "tenant": type(
                    "Tenant",
                    (),
                    {
                        "nom": "Lycée Horizon",
                        "type": "lycee",
                        "couleur_primaire": "#112233",
                        "couleur_secondaire": "#FFFFFF",
                        "get_type_display": lambda self: "Lycée",
                    },
                )(),
            },
        )()
        report = {
            "code": "notes-secondary",
            "label": "Notes secondaire",
            "dataset": "notes",
            "fields": ["matricule", "note"],
            "allowed_filters": ["classe"],
            "formats": ["csv", "xlsx", "pdf"],
        }

        response = export_queryset(
            request,
            FakeQuerySet(),
            report,
            {"matricule": ("Matricule", "eleve__matricule"), "note": ("Note", "valeur")},
            {"classe": "evaluation__classe_id"},
            {"classe": 9},
        )

        assert response.status_code == 200
        content = response.content.decode()
        assert "Établissement,Lycée Horizon" in content
        assert "Rapport,Notes secondaire" in content
        assert "Matricule,Note" in content
        assert "MAT-001,14.5" in content

    def test_export_queryset_rejects_unauthorized_format(self):
        request = type(
            "Request",
            (),
            {
                "data": {"format": "pdf"},
                "user": FakeUser(),
                "tenant": type("Tenant", (), {"nom": "Lycée"})(),
            },
        )()
        report = {
            "code": "notes-secondary",
            "label": "Notes secondaire",
            "dataset": "notes",
            "fields": ["matricule"],
            "allowed_filters": [],
            "formats": ["csv"],
        }

        with pytest.raises(ValidationError):
            export_queryset(
                request,
                type(
                    "QuerySet",
                    (),
                    {
                        "filter": lambda self, **_kwargs: self,
                        "values_list": lambda self, *_fields: self,
                        "distinct": lambda self: [],
                    },
                )(),
                report,
                {"matricule": ("Matricule", "eleve__matricule")},
                {},
                {},
            )
