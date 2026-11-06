from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from apps.core.models import ModuleConfiguration, Reclamation, WorkflowEvent
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from django.conf import settings
from django.contrib.auth import get_user_model
from django_tenants.utils import schema_context
from rest_framework.exceptions import PermissionDenied

from sis_common.module_registry import module_snapshot, require_module

BASE = "/api/v1/etablissement/current/modules/"
COMPLAINTS = "/api/v1/core/reclamations/"


class ModuleDependencyTests(TestCase):
    def test_persisted_disabled_dependency_blocks_dependent_modules(self):
        tenant = SimpleNamespace(pk=11)
        configuration = SimpleNamespace(
            revision=3,
            enabled={"core.notifications": False, "sis.complaints": True, "sis.delegations": True},
        )
        with patch("sis_common.module_registry.module_configuration", return_value=configuration):
            snapshot = module_snapshot(tenant)
            self.assertFalse(snapshot["enabled"]["core.notifications"])
            for identifier in ("sis.complaints", "sis.delegations"):
                with self.subTest(identifier=identifier):
                    self.assertFalse(snapshot["enabled"][identifier])
                    self.assertFalse(
                        next(item["enabled"] for item in snapshot["modules"] if item["identifier"] == identifier)
                    )
                    with self.assertRaises(PermissionDenied):
                        require_module(tenant, identifier)


class ModuleConfigurationTests(TenantAPITestCase):
    def setUp(self):
        user_model = get_user_model()
        self.admin = user_model.objects.create_user(
            "module-admin", etablissement=self.tenant, is_superuser=True, role="super_admin"
        )
        self.learner = user_model.objects.create_user(
            "module-learner",
            etablissement=self.tenant,
            role="eleve" if settings.SIS_VARIANT == "secondaire" else "etudiant",
        )
        self.client.force_authenticate(self.admin)
        self.payload = {
            "revision": 0,
            "enabled": {"sis.complaints": False},
            "reason": "Suspension temporaire du service",
        }

    def test_preview_activation_reactivation_and_conflict_preserve_records(self):
        self.client.force_authenticate(self.learner)
        complaint = self.client.post(
            COMPLAINTS, {"categorie": "autre", "objet": "Demande", "description": "Privée"}, format="json"
        )
        assert complaint.status_code == 201
        self.client.force_authenticate(self.admin)
        preview = self.client.post(BASE, self.payload, format="json")
        assert preview.status_code == 200, preview.data
        assert preview.data["saved"] is False
        assert not ModuleConfiguration.objects.exists()
        assert self.client.get(COMPLAINTS).status_code == 200
        changed = self.client.patch(BASE, self.payload, format="json")
        assert changed.status_code == 200, changed.data
        assert changed.data["revision"] == 1
        assert self.client.get(COMPLAINTS).status_code == 403
        assert Reclamation.objects.filter(pk=complaint.data["id"]).exists()
        assert self.client.patch(BASE, self.payload, format="json").status_code == 409
        events = WorkflowEvent.objects.filter(action="configuration_modules")
        assert events.count() == 1
        assert events.get().actor == self.admin
        assert events.get().message == self.payload["reason"]
        response = self.client.patch(
            BASE, {**self.payload, "revision": 1, "enabled": {"sis.complaints": True}}, format="json"
        )
        assert response.status_code == 200
        self.client.force_authenticate(self.learner)
        assert self.client.get(f"{COMPLAINTS}{complaint.data['id']}/").status_code == 200

    def test_configuration_rejects_unknown_modules_types_required_modules_and_unauthorized_users(self):
        for enabled in ({"untrusted.plugin": True}, {"sis.complaints": "false"}, {"core.notifications": False}, []):
            response = self.client.patch(BASE, {**self.payload, "enabled": enabled}, format="json")
            assert response.status_code == 400, response.data
        assert self.client.patch(BASE, {**self.payload, "reason": " "}, format="json").status_code == 400
        assert self.client.patch(BASE, {**self.payload, "package": "external.zip"}, format="json").status_code == 400
        assert not ModuleConfiguration.objects.exists()
        self.client.force_authenticate(self.learner)
        for method in (self.client.get, self.client.post, self.client.patch):
            response = method(BASE, self.payload, format="json") if method != self.client.get else method(BASE)
            assert response.status_code == 403
        self.client.force_authenticate(self.admin)
        assert self.client.patch(BASE, self.payload, format="json").status_code == 200
        self.client.force_authenticate(self.learner)
        assert self.client.get(COMPLAINTS).status_code == 403
        assert self.client.post(COMPLAINTS, {}, format="json").status_code == 403
        capabilities = self.client.get("/api/v1/utilisateurs/comptes/capabilities/")
        assert capabilities.status_code == 200, capabilities.data
        assert capabilities.data["modules"]["sis.complaints"] is False

    def test_audit_failure_rolls_back_the_activation(self):
        with patch("sis_common.module_configuration.record_workflow_event", side_effect=RuntimeError("audit failure")):
            with self.assertRaises(RuntimeError):
                self.client.patch(BASE, self.payload, format="json")
        assert not ModuleConfiguration.objects.exists()
        assert self.client.get(COMPLAINTS).status_code == 200

    def test_persisted_disabled_dependency_blocks_complaints(self):
        ModuleConfiguration.objects.create(
            etablissement=self.tenant, enabled={"core.notifications": False, "sis.complaints": True}
        )
        snapshot = self.client.get(BASE)
        assert snapshot.status_code == 200, snapshot.data
        assert snapshot.data["enabled"]["sis.complaints"] is False
        self.client.force_authenticate(self.learner)
        assert self.client.get(COMPLAINTS).status_code == 403

    def test_other_establishment_configuration_does_not_change_this_tenant(self):
        other = type(self.tenant)(
            schema_name="modules_other",
            nom="Autre",
            type=self.tenant.type,
            adresse=self.tenant.adresse,
            code_postal=self.tenant.code_postal,
            ville=self.tenant.ville,
            telephone=self.tenant.telephone,
            email="modules-other@example.test",
        )
        other.auto_create_schema = False
        with schema_context("public"):
            other.save()
        ModuleConfiguration.objects.create(etablissement=other, enabled={"sis.complaints": False})
        assert module_snapshot(other)["enabled"]["sis.complaints"] is False
        assert self.client.get(BASE).data["enabled"]["sis.complaints"] is True
        self.admin.etablissement = other
        self.admin.save(update_fields=["etablissement"])
        assert self.client.patch(BASE, self.payload, format="json").status_code == 403
