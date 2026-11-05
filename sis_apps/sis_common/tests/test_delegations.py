from datetime import timedelta
from unittest.mock import patch

import pytest
from django.apps import apps
from django.contrib.auth.models import Permission
from django.utils import timezone

from sis_common.tests.test_grade_entry import GradeEntryFixture


class DelegationTests(GradeEntryFixture):
    def setUp(self):
        super().setUp()
        self.resource = "classes" if self.secondary else "formations"
        self.parent = self.classe if self.secondary else self.formation
        self.other = self.create(
            "classes.Classe" if self.secondary else "formations.Formation",
            **(
                {
                    "nom": "Classe de mission",
                    "etablissement": self.tenant,
                    "niveau": self.classe.niveau,
                    "annee_scolaire": self.year,
                }
                if self.secondary
                else {"code": "F-MISSION", "nom": "Formation de mission", "type": "licence"}
            ),
        )
        self.base = "/api/v1/core/delegations/"
        self.now = timezone.now()
        self.payload = {
            "beneficiaire": self.learners[0].user_id,
            "ressource": self.resource,
            "dossiers_ids": [self.other.pk],
            "debut": (self.now - timedelta(hours=1)).isoformat(),
            "fin": (self.now + timedelta(hours=1)).isoformat(),
            "motif": "Stage au service de scolarité",
        }

    def grant(self):
        response = self.client.post(self.base, self.payload, format="json")
        assert response.status_code == 201, response.data
        return f"{self.base}{response.data['id']}/"

    def test_scoped_extra_access_keeps_learner_role_and_is_not_a_crud_permission(self):
        url = self.grant()
        user = self.learners[0].user
        detail = self.client.get(url).data
        assert detail["responsable_nom"] == self.admin.username
        assert detail["beneficiaire_nom"] == user.get_full_name()
        notification = apps.get_model("core.WorkflowNotification").objects.get(category="delegation_accordee")
        assert notification.recipient_id == user.pk
        self.client.force_authenticate(user)
        assert self.client.get(self.base).data["count"] == 1
        response = self.client.get(f"{url}dossiers/")
        assert response.status_code == 200
        assert [row["id"] for row in response.data["results"]] == [self.other.pk]
        assert self.client.post(self.base, self.payload, format="json").status_code == 403
        assert self.client.patch(url, {"dossiers_ids": [self.parent.pk]}, format="json").status_code == 405
        assert self.client.post(f"{url}dossiers/", {}, format="json").status_code == 405
        legacy = "classes/classes" if self.secondary else "formations/formations"
        assert self.client.get(f"/api/v1/{legacy}/{self.other.pk}/").status_code == 404
        user.refresh_from_db()
        assert user.role == ("eleve" if self.secondary else "etudiant")
        assert not user.is_staff and not user.get_all_permissions()
        self.client.force_authenticate(self.learners[1].user)
        assert self.client.get(url).status_code == 404
        assert self.client.get(f"{url}dossiers/").status_code == 404
        assert self.client.get(f"{url}historique/").status_code == 404

    def test_future_expired_and_revoked_missions_cannot_be_used(self):
        url = self.grant()
        self.client.force_authenticate(self.learners[0].user)
        for instant in [self.now - timedelta(hours=2), self.now + timedelta(hours=2)]:
            with patch("django.utils.timezone.now", return_value=instant):
                assert self.client.get(f"{url}dossiers/").status_code == 403
        self.client.force_authenticate(self.admin)
        assert self.client.post(f"{url}revoquer/", {"motif": ""}, format="json").status_code == 400
        assert self.client.post(f"{url}revoquer/", {"motif": "Mission terminée"}, format="json").status_code == 200
        self.client.force_authenticate(self.learners[0].user)
        assert self.client.get(url).data["statut"] == "revoquee"
        assert self.client.get(f"{url}dossiers/").status_code == 403
        assert (
            apps.get_model("core.WorkflowNotification")
            .objects.filter(category="delegation_revoquee", recipient=self.learners[0].user)
            .count()
            == 1
        )

    def test_module_suspension_blocks_direct_access_and_preserves_missions_for_reactivation(self):
        url = self.grant()
        modules = "/api/v1/etablissement/current/modules/"
        change = {
            "revision": 0,
            "enabled": {"sis.delegations": False},
            "reason": "Suspension du service de missions",
        }
        preview = self.client.post(modules, change, format="json")
        assert preview.status_code == 200, preview.data
        assert preview.data["saved"] is False
        assert self.client.get(f"{url}dossiers/").status_code == 200
        response = self.client.patch(modules, change, format="json")
        assert response.status_code == 200, response.data
        assert response.data["enabled"]["sis.delegations"] is False
        assert self.client.post(self.base, self.payload, format="json").status_code == 403
        assert self.client.get(f"{self.base}choix/").status_code == 403

        self.client.force_authenticate(self.learners[0].user)
        for endpoint in (self.base, url, f"{url}dossiers/", f"{url}historique/"):
            assert self.client.get(endpoint).status_code == 403
        assert apps.get_model("core.AccessDelegation").objects.count() == 1
        capabilities = self.client.get("/api/v1/utilisateurs/comptes/capabilities/")
        assert capabilities.data["modules"]["sis.delegations"] is False

        self.client.force_authenticate(self.admin)
        restored = self.client.patch(
            modules, {**change, "revision": 1, "enabled": {"sis.delegations": True}}, format="json"
        )
        assert restored.status_code == 200, restored.data
        self.client.force_authenticate(self.learners[0].user)
        assert self.client.get(f"{url}dossiers/").status_code == 200
        assert self.client.get(url).data["statut"] == "active"

    def test_staff_flag_invalid_recipient_and_invalid_bounds_never_grant_access(self):
        self.teacher.is_staff = True
        self.client.force_authenticate(self.teacher)
        assert self.client.post(self.base, self.payload, format="json").status_code == 403
        self.client.force_authenticate(self.admin)
        for changes in [
            {"beneficiaire": self.admin.pk},
            {"dossiers_ids": []},
            {"dossiers_ids": [999999]},
            {"ressource": "utilisateurs"},
            {"fin": self.payload["debut"]},
        ]:
            assert self.client.post(self.base, {**self.payload, **changes}, format="json").status_code == 400
        assert not apps.get_model("core.AccessDelegation").objects.exists()

    def test_grantor_scopes_and_loss_of_authority_are_enforced(self):
        permission = "classes.view_classe" if self.secondary else "formations.view_formation"
        for value in ["core.manage_accessdelegation", permission]:
            app, code = value.split(".")
            self.teacher.user_permissions.add(Permission.objects.get(content_type__app_label=app, codename=code))
        self.teacher.attributs_acces = {"permission_scopes": {permission: {self.resource: [self.other.pk]}}}
        self.teacher.save(update_fields=["attributs_acces"])
        self.client.force_authenticate(self.teacher)
        choice = self.client.get(f"{self.base}choix/", {"ressource": self.resource})
        assert [item["id"] for item in choice.data["results"]] == [self.other.pk]
        invalid = self.client.post(self.base, {**self.payload, "dossiers_ids": [self.parent.pk]}, format="json")
        assert invalid.status_code == 400
        url = self.grant()
        self.teacher.user_permissions.clear()
        self.client.force_authenticate(self.learners[0].user)
        assert self.client.get(f"{url}dossiers/").status_code == 403

    def test_missing_mandatory_notification_rolls_back_the_grant(self):
        notifications = apps.get_model("core.WorkflowNotification")
        with patch.object(notifications.objects, "create", side_effect=RuntimeError("notification unavailable")):
            with pytest.raises(RuntimeError, match="notification unavailable"):
                self.client.post(self.base, self.payload, format="json")
        assert not apps.get_model("core.AccessDelegation").objects.exists()
        assert not apps.get_model("core.WorkflowEvent").objects.filter(action="delegation_accordee").exists()
