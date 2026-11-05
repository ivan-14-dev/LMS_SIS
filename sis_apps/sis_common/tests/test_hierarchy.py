from copy import deepcopy
from datetime import timedelta
from unittest.mock import patch

from django.apps import apps
from django.utils import timezone
from django_tenants.utils import schema_context

from sis_common.hierarchy import OFFERING_SETTING, resolve_configuration
from sis_common.tests.test_grade_entry import GradeEntryFixture
from sis_common.tests.test_institutional_profiles import offering

BASE = "/api/v1/etablissement/current/hierarchy/"
UNITS = "/api/v1/etablissement/unites/"


class HierarchicalConfigurationTests(GradeEntryFixture):
    def unit(self, code, kind="campus", parent=None):
        response = self.client.post(
            UNITS, {"code": code, "nom": code, "kind": kind, "parent": parent.pk if parent else None}, format="json"
        )
        assert response.status_code == 201, response.data
        return apps.get_model("core.OrganizationUnit").objects.get(pk=response.data["id"])

    def publication_payload(self, value, unit=None, **extra):
        return {
            "base_revision": self.client.get(BASE).data["revision"],
            "unit": unit.pk if unit else None,
            "values": {OFFERING_SETTING: value},
            "locks": [],
            "reason": "Publication de recette",
            **extra,
        }

    def publish(self, value, unit=None, **extra):
        response = self.client.patch(BASE, self.publication_payload(value, unit, **extra), format="json")
        assert response.status_code == 201, response.data
        return response

    def create_parent(self, code, unit=None, **extra):
        if self.secondary:
            url = "/api/v1/classes/classes/"
            data = {"nom": code, "niveau": self.classe.niveau_id, "annee_scolaire": self.year.pk}
        else:
            url = "/api/v1/formations/formations/"
            data = {"nom": code, "code": code, "type": "licence"}
        return self.client.post(url, {**data, "organisation_unit": unit.pk if unit else None, **extra}, format="json")

    def test_mixed_profile_inheritance_is_bound_to_new_groups_without_rewriting_existing_ones(self):
        parent = self.classe if self.secondary else self.formation
        original = deepcopy(parent.offre_configuration)
        created = []
        for profile in ("primary", "secondary", "higher_education", "vocational"):
            unit = self.unit(profile)
            self.publish(offering(profile), unit)
            response = self.create_parent(f"group-{profile}", unit)
            assert response.status_code == 201, response.data
            assert response.data["offre_configuration"] == offering(profile)
            assert response.data["configuration_origine"]["source"]["unit"] == unit.pk
            created.append((response.data["id"], offering(profile)))
        self.publish(offering("custom"))
        parent.refresh_from_db()
        assert parent.offre_configuration == original
        model = apps.get_model("classes.Classe" if self.secondary else "formations.Formation")
        for identifier, saved in created:
            assert model.objects.get(pk=identifier).offre_configuration == saved

    def test_parent_locks_take_precedence_and_preview_explains_suppressed_overrides(self):
        campus = self.unit("campus")
        department = self.unit("dept", "department", campus)
        program = self.unit("program", "program", department)
        self.publish(offering("secondary"))
        self.publish(offering("vocational"), program)
        payload = self.publication_payload(offering("primary"), campus, locks=[OFFERING_SETTING])
        preview = self.client.post(BASE, payload, format="json")
        assert preview.status_code == 200, preview.data
        assert preview.data["saved"] is False
        assert preview.data["impacts"][0]["unit"] == program.pk
        assert resolve_configuration(self.tenant, program)["values"][OFFERING_SETTING]["profile"] == "vocational"
        assert self.client.patch(BASE, payload, format="json").status_code == 201
        resolved = resolve_configuration(self.tenant, program)
        assert resolved["values"][OFFERING_SETTING]["profile"] == "primary"
        assert resolved["locks"][OFFERING_SETTING]["unit"] == campus.pk
        assert resolved["ignored_overrides"][0]["unit"] == program.pk
        assert (
            self.client.patch(BASE, self.publication_payload(offering("custom"), program), format="json").status_code
            == 400
        )
        assert self.create_parent("forbidden", program, offre_code="custom").status_code == 400
        response = self.create_parent("inherited", program)
        assert response.status_code == 201, response.data
        assert response.data["offre_configuration"]["profile"] == "primary"
        url = "/api/v1/classes/classes/" if self.secondary else "/api/v1/formations/formations/"
        assert self.client.patch(f"{url}{response.data['id']}/", {"offre_code": ""}, format="json").status_code == 400
        assert (
            self.client.patch(
                f"{url}{response.data['id']}/", {"organisation_unit": campus.pk}, format="json"
            ).status_code
            == 400
        )

    def test_future_publication_and_removing_local_override_preserve_historical_resolution(self):
        campus = self.unit("campus")
        self.publish(offering("secondary"))
        first = timezone.now()
        future = first + timedelta(days=2)
        self.publish(offering("primary"), effective_from=future.isoformat())
        assert resolve_configuration(self.tenant, campus)["values"][OFFERING_SETTING]["profile"] == "secondary"
        assert resolve_configuration(self.tenant, campus, future)["values"][OFFERING_SETTING]["profile"] == "primary"
        self.publish(None, campus)
        assert resolve_configuration(self.tenant, campus)["values"][OFFERING_SETTING] is None
        payload = self.publication_payload(None, campus, values={})
        assert self.client.patch(BASE, payload, format="json").status_code == 201
        assert resolve_configuration(self.tenant, campus)["values"][OFFERING_SETTING]["profile"] == "secondary"
        assert resolve_configuration(self.tenant, campus, first)["values"][OFFERING_SETTING]["profile"] == "secondary"
        response = self.client.get(BASE, {"at": future.isoformat(), "unit": campus.pk})
        assert response.status_code == 200
        assert response.data["effective"]["values"][OFFERING_SETTING]["profile"] == "primary"
        past = self.publication_payload(None, effective_from=(first - timedelta(days=1)).isoformat())
        assert self.client.patch(BASE, past, format="json").status_code == 400

    def test_publication_rejects_invalid_types_stale_revision_and_audit_failure(self):
        payload = self.publication_payload(offering("secondary"))
        for changes in (
            {"values": {"unknown": True}},
            {"values": []},
            {"locks": [OFFERING_SETTING, OFFERING_SETTING]},
            {"values": {OFFERING_SETTING: {"profile": "unknown"}}},
            {"reason": " "},
            {"published_by": self.teacher.pk},
            {
                "values": {
                    OFFERING_SETTING: {
                        **offering("secondary"),
                        "assessment": {"mode": "numeric", "minimum": 0, "maximum": 10000, "pass_mark": 5000},
                    }
                }
            },
        ):
            assert self.client.patch(BASE, {**payload, **changes}, format="json").status_code == 400
        model = apps.get_model("core.ConfigurationRevision")
        assert model.objects.count() == 0
        with patch("sis_common.hierarchy_api.record_workflow_event", side_effect=RuntimeError("audit unavailable")):
            with self.assertRaises(RuntimeError):
                self.client.patch(BASE, payload, format="json")
        assert model.objects.count() == 0
        assert self.client.patch(BASE, payload, format="json").status_code == 201
        assert self.client.patch(BASE, payload, format="json").status_code == 409
        assert model.objects.count() == 1
        event = apps.get_model("core.WorkflowEvent").objects.get(action="publication_configuration")
        assert event.actor_id == self.admin.pk
        assert event.message == payload["reason"]

    def test_locked_rule_cannot_be_replaced_by_catalogue_edits_or_forged_provenance(self):
        published = offering("secondary")
        self.publish(published, locks=[OFFERING_SETTING])
        edited = deepcopy(published)
        edited["assessment"]["pass_mark"] = 5
        self.tenant.configuration_academique["learning_offerings"] = [edited]
        self.tenant.save(update_fields=["configuration_academique"])
        response = self.create_parent("locked", offre_code=published["code"], configuration_origine={"locked": False})
        assert response.status_code == 201, response.data
        assert response.data["offre_configuration"] == published
        assert response.data["configuration_origine"]["locked"] is True
        url = "/api/v1/classes/classes/" if self.secondary else "/api/v1/formations/formations/"
        response = self.client.patch(
            f"{url}{response.data['id']}/",
            {"configuration_origine": {"locked": False}, "offre_configuration": edited},
            format="json",
        )
        assert response.status_code == 200, response.data
        assert response.data["offre_configuration"] == published
        assert response.data["configuration_origine"]["locked"] is True

    def test_an_unlocked_explicit_choice_replaces_the_inherited_provenance(self):
        self.publish(offering("secondary"))
        chosen = offering("vocational")
        self.tenant.configuration_academique["learning_offerings"] = [chosen]
        self.tenant.save(update_fields=["configuration_academique"])
        response = self.create_parent("explicit", offre_code=chosen["code"])
        assert response.status_code == 201, response.data
        assert response.data["configuration_origine"]["inherited"] is False
        response = self.create_parent("inherited")
        assert response.status_code == 201, response.data
        assert response.data["configuration_origine"]["inherited"] is True
        url = "/api/v1/classes/classes/" if self.secondary else "/api/v1/formations/formations/"
        response = self.client.patch(f"{url}{response.data['id']}/", {"offre_code": chosen["code"]}, format="json")
        assert response.status_code == 200, response.data
        assert response.data["offre_configuration"] == chosen
        assert response.data["configuration_origine"]["source"]["scope"] == "explicit"
        assert response.data["configuration_origine"]["inherited"] is False

    def test_unit_topology_and_configuration_permissions_are_tenant_bound(self):
        campus = self.unit("campus")
        program = self.unit("program", "program", campus)
        data = {"code": "wrong", "nom": "Wrong", "kind": "campus", "parent": program.pk}
        assert self.client.post(UNITS, data, format="json").status_code == 400
        assert self.client.patch(f"{UNITS}{campus.pk}/", {"parent": program.pk}, format="json").status_code == 400
        assert self.client.delete(f"{UNITS}{campus.pk}/").status_code == 405
        foreign = type(self.tenant)(schema_name="hierarchy_foreign")
        self.setup_tenant(foreign)
        foreign.auto_create_schema = False
        with schema_context("public"):
            foreign.save()
        foreign_unit = apps.get_model("core.OrganizationUnit").objects.create(
            etablissement=foreign, code="foreign", nom="Foreign", kind="campus"
        )
        assert self.client.get(BASE, {"unit": foreign_unit.pk}).status_code == 400
        assert self.create_parent("foreign", foreign_unit).status_code == 400
        self.client.force_authenticate(self.teacher)
        assert self.client.get(BASE).status_code == 403
        assert self.client.post(BASE, {}, format="json").status_code == 403
        assert self.client.patch(BASE, {}, format="json").status_code == 403
        assert self.client.post(UNITS, data, format="json").status_code == 403
