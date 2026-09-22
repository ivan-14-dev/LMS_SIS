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
