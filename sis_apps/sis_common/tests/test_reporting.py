from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError

from sis_common.reporting import configured_report


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

        with self.assertRaises(ValidationError):
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

        with self.assertRaises(ValidationError):
            configured_report(request, "payments", allowed_datasets={"financial_payments"})
