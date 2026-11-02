from copy import deepcopy

import pytest
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.utilisateurs.models import Utilisateur
from django.core.exceptions import ValidationError
from django_tenants.utils import schema_context

from sis_common.academic_configuration import default_academic_configuration, merge_academic_configuration
from sis_common.institutional_profiles import (
    institutional_profile_schema,
    preview_offering_result,
    validate_learning_offering,
    validate_learning_offerings,
)

CURRENT = "/api/v1/etablissement/current/"
PREVIEW = f"{CURRENT}offering-preview/"


def offering(profile):
    return next(item["template"] for item in institutional_profile_schema()["profiles"] if item["code"] == profile)


def test_four_profiles_and_mixed_offers_preserve_legacy_rules():
    current = default_academic_configuration()
    current.pop("learning_offerings")
    current["grading_scale"]["maximum"] = 100
    offers = [offering(code) for code in ("primary", "secondary", "higher_education", "vocational")]
    merged = merge_academic_configuration(current, {"learning_offerings": offers})
    assert merged["grading_scale"] == current["grading_scale"]
    assert merged["learning_offerings"] == offers
    assert "learning_offerings" not in current
    assert offers[0]["credits"] is None
    assert offers[3]["calendar"] == "session"
    assert merge_academic_configuration(merged, {"language": "en"})["learning_offerings"] == offers


@pytest.mark.parametrize(
    "changes",
    [
        {"version": True},
        {"version": 2},
        {"profile": "unknown"},
        {"profile": []},
        {"calendar": {}},
        {"credits": {"system": "Local", "target": 0}},
        {"assessment": {"mode": "numeric", "minimum": 0, "maximum": "NaN", "pass_mark": 10}},
        {"assessment": {"mode": "numeric", "minimum": 0, "maximum": 20, "pass_mark": 21}},
        {"assessment": {"mode": "numeric", "minimum": False, "maximum": 20, "pass_mark": 10}},
        {"assessment": {"mode": "competency", "criteria": []}},
        {"unknown": "unsupported"},
    ],
)
def test_invalid_or_future_offers_are_rejected(changes):
    with pytest.raises(ValidationError):
        validate_learning_offering({**offering("secondary"), **changes})


def test_duplicate_offer_and_competency_codes_are_rejected():
    item = offering("primary")
    with pytest.raises(ValidationError):
        validate_learning_offerings([item, deepcopy(item)])
    item["assessment"]["criteria"] *= 2
    with pytest.raises(ValidationError):
        validate_learning_offering(item)


def test_custom_profile_can_use_any_supported_calendar_and_scale():
    item = offering("custom")
    item["calendar"] = "session"
    item["assessment"] = {"mode": "numeric", "minimum": 0, "maximum": 100, "pass_mark": 75}
    item["terminology"]["learner"] = "Salarié"
    validate_learning_offering(item)
    assert preview_offering_result(item, {"score": "74.5"})["status"] == "failed"
    assert preview_offering_result(item, {"score": 75})["status"] == "passed"


@pytest.mark.parametrize("score, expected", [(None, "incomplete"), (0, "failed"), ("10.0", "passed")])
def test_numeric_policy_distinguishes_missing_zero_and_threshold(score, expected):
    assert preview_offering_result(offering("secondary"), {"score": score})["status"] == expected


@pytest.mark.parametrize("score", [-1, 21, "Infinity", True, {}, ""])
def test_preview_rejects_invalid_scores(score):
    with pytest.raises(ValidationError):
        preview_offering_result(offering("secondary"), {"score": score})


def test_competency_policy_requires_every_criterion_and_rejects_unknown_ones():
    item = offering("vocational")
    item["assessment"]["criteria"].append({"code": "safety", "label": "Sécurité"})
    assert preview_offering_result(item, {"criteria": {"competence_1": True}})["status"] == "incomplete"
    assert preview_offering_result(item, {"criteria": {"competence_1": True, "safety": False}})["status"] == "failed"
    assert preview_offering_result(item, {"criteria": {"competence_1": True, "safety": True}})["status"] == "passed"
    with pytest.raises(ValidationError):
        preview_offering_result(item, {"criteria": {"unknown": True}})
    with pytest.raises(ValidationError):
        preview_offering_result(item, {"criteria": {"competence_1": 1}})


def test_pass_fail_policy_does_not_infer_a_decision_from_truthiness():
    item = offering("custom")
    for value, expected in ((None, "incomplete"), (False, "failed"), (True, "passed")):
        assert preview_offering_result(item, {"passed": value})["status"] == expected
    with pytest.raises(ValidationError):
        preview_offering_result(item, {"passed": "false"})


class InstitutionalProfilesAPITests(TenantAPITestCase):
    def setUp(self):
        self.admin = Utilisateur.objects.create_superuser(
            username="profiles-admin",
            email="profiles@example.test",
            password="Profiles-test-password-924!",
            role="super_admin",
            etablissement=self.tenant,
        )
        self.client.force_authenticate(self.admin)
        self.tenant.configuration_academique = default_academic_configuration()
        self.tenant.configuration_academique.pop("learning_offerings")
        self.tenant.save(update_fields=["configuration_academique"])

    def test_roundtrip_mixed_offerings_is_tenant_bound_and_preserves_existing_settings(self):
        foreign = type(self.tenant)(schema_name="profiles_foreign")
        self.setup_tenant(foreign)
        foreign.auto_create_schema = False
        with schema_context("public"):
            foreign.save()
        original_foreign = deepcopy(foreign.configuration_academique)
        original = deepcopy(self.tenant.configuration_academique)
        response = self.client.get(CURRENT)
        assert response.status_code == 200
        assert len(response.data["configuration_schema"]["institutional_profiles"]["profiles"]) == 5
        offers = [offering(code) for code in ("primary", "secondary", "higher_education", "vocational")]
        response = self.client.patch(
            CURRENT,
            {"id": foreign.pk, "configuration_academique": {"learning_offerings": offers}},
            format="json",
        )
        assert response.status_code == 200, response.data
        self.tenant.refresh_from_db()
        foreign.refresh_from_db()
        assert self.tenant.configuration_academique["learning_offerings"] == offers
        assert self.tenant.configuration_academique["grading_scale"] == original["grading_scale"]
        assert foreign.configuration_academique == original_foreign
        assert self.client.get(CURRENT).data["configuration_academique"]["learning_offerings"] == offers

    def test_invalid_configuration_does_not_partially_save_other_fields(self):
        original = deepcopy(self.tenant.configuration_academique)
        original_name = self.tenant.nom
        offers = [offering("primary"), {**offering("secondary"), "version": 99}]
        response = self.client.patch(
            CURRENT,
            {"nom": "Must not change", "configuration_academique": {"learning_offerings": offers}},
            format="json",
        )
        assert response.status_code == 400, response.data
        self.tenant.refresh_from_db()
        assert self.tenant.configuration_academique == original
        assert self.tenant.nom == original_name
        for invalid in ([], "invalid", None):
            response = self.client.patch(CURRENT, {"configuration_academique": invalid}, format="json")
            assert response.status_code == 400, response.data

    def test_preview_calculates_without_persisting_and_is_post_only(self):
        original = deepcopy(self.tenant.configuration_academique)
        response = self.client.post(PREVIEW, {"offering": offering("secondary"), "result": {"score": 0}}, format="json")
        assert response.status_code == 200, response.data
        assert response.data["status"] == "failed"
        response = self.client.post(
            PREVIEW, {"offering": offering("secondary"), "result": {"score": 25}}, format="json"
        )
        assert response.status_code == 400, response.data
        self.tenant.refresh_from_db()
        assert self.tenant.configuration_academique == original
        assert self.client.get(PREVIEW).status_code == 405
        assert self.client.patch(PREVIEW, {"nom": "Forbidden"}, format="json").status_code == 405

    def test_teacher_cannot_read_modify_or_preview_institutional_configuration(self):
        teacher = Utilisateur.objects.create_user("profiles-teacher", role="enseignant", etablissement=self.tenant)
        self.client.force_authenticate(teacher)
        assert self.client.get(CURRENT).status_code == 403
        assert self.client.patch(CURRENT, {"nom": "Forbidden"}, format="json").status_code == 403
        assert (
            self.client.post(
                PREVIEW, {"offering": offering("custom"), "result": {"passed": True}}, format="json"
            ).status_code
            == 403
        )
