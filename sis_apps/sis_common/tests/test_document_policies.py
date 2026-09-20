from unittest.mock import patch

from django.test import SimpleTestCase
from sis_common.document_policies import enforce_financial_clearance


class FakeTenant:
    configuration_academique = {}

    def __init__(self, tenant_id=1):
        self.id = tenant_id


class FakeRequest:
    def __init__(self):
        self.tenant = FakeTenant()


class FakeView:
    def __init__(self, obj):
        self.obj = obj
        self.calls = 0

    def get_object(self):
        self.calls += 1
        return self.obj


class DocumentPoliciesTests(SimpleTestCase):
    def test_decorator_blocks_action_when_financial_clearance_is_missing(self):
        decorated = enforce_financial_clearance(
            candidates_getter=lambda _view, _request, obj: [{"scope": "tenant", "context": {"id": obj.id}}],
            subject_getter=lambda _view, _request, obj: obj,
            academic_year_ids_getter=lambda _view, _request, _obj: [1],
            invoice_model_label="paiements.Facture",
            invoice_subject_field="eleve",
            invoice_year_lookup="type_frais__annee_scolaire_id",
            message="blocked",
        )(lambda _view, _request, *_args, **_kwargs: "ok")

        with patch("sis_common.document_policies.requires_financial_clearance", return_value=True), patch(
            "sis_common.document_policies.subject_has_financial_clearance",
            return_value=False,
        ):
            response = decorated(FakeView(type("Obj", (), {"id": 7})()), FakeRequest())

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["error"], "blocked")

    def test_decorator_allows_action_when_clearance_is_not_required(self):
        decorated = enforce_financial_clearance(
            candidates_getter=lambda _view, _request, obj: [{"scope": "tenant", "context": {"id": obj.id}}],
            subject_getter=lambda _view, _request, obj: obj,
            academic_year_ids_getter=lambda _view, _request, _obj: [1],
            invoice_model_label="paiements.Facture",
            invoice_subject_field="eleve",
            invoice_year_lookup="type_frais__annee_scolaire_id",
            message="blocked",
        )(lambda view, _request, *_args, **_kwargs: view.obj.id)

        with patch("sis_common.document_policies.requires_financial_clearance", return_value=False):
            result = decorated(FakeView(type("Obj", (), {"id": 9})()), FakeRequest())

        self.assertEqual(result, 9)
