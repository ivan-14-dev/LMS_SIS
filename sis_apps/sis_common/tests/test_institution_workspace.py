import uuid

from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.utilisateurs.models import Utilisateur
from rest_framework.authtoken.models import Token

WORKSPACE = "/api/v1/etablissement/current/workspace/"
LINK = "/api/v1/utilisateurs/comptes/workspace-link/"


class InstitutionWorkspaceTests(TenantAPITestCase):
    def setUp(self):
        self.root = Utilisateur.objects.create_superuser("workspace-root", etablissement=self.tenant)
        self.user = Utilisateur.objects.create_user("workspace-user", etablissement=self.tenant)
        self.peer = str(uuid.uuid4())
        self.login(self.root)

    def login(self, user):
        self.client.force_authenticate(None)
        token, _ = Token.objects.get_or_create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def declaration(self, **changes):
        snapshot = self.client.get(WORKSPACE).data
        return {"version": snapshot["version"], "peer": self.peer, "home": snapshot["id"], **changes}

    def test_only_tenant_superuser_can_declare_and_versions_prevent_lost_updates(self):
        data = self.declaration()
        self.login(self.user)
        assert self.client.put(WORKSPACE, data, format="json").status_code == 403
        self.login(self.root)
        response = self.client.put(WORKSPACE, data, format="json")
        assert response.status_code == 200, response.data
        assert response.data["peer"] == self.peer
        assert response.data["version"] != data["version"]
        assert self.client.put(WORKSPACE, data, format="json").status_code == 409
        assert self.client.put(WORKSPACE, self.declaration(peer=None, home=None), format="json").status_code == 200
        reattached = self.client.put(WORKSPACE, self.declaration(), format="json")
        assert reattached.status_code == 200
        assert reattached.data["version"] != response.data["version"]

    def test_self_or_inconsistent_institution_links_are_rejected(self):
        snapshot = self.client.get(WORKSPACE).data
        for changes in ({"peer": snapshot["id"]}, {"home": str(uuid.uuid4())}, {"peer": None}):
            response = self.client.put(WORKSPACE, self.declaration(**changes), format="json")
            assert response.status_code == 400, response.data
        assert self.client.get(WORKSPACE).data["peer"] is None

    def test_linking_self_preserves_policy_and_confers_no_permissions(self):
        assert self.client.put(WORKSPACE, self.declaration(), format="json").status_code == 200
        self.user.attributs_acces = {
            "access_policy": {"denied_permissions": ["utilisateurs.change_utilisateur"]},
            "department": "unchanged",
        }
        self.user.save()
        self.login(self.user)
        response = self.client.put(LINK, {"peer": self.peer, "user": 999}, format="json")
        assert response.status_code == 200, response.data
        self.user.refresh_from_db()
        assert self.user.attributs_acces["department"] == "unchanged"
        assert self.user.attributs_acces["access_policy"]["denied_permissions"] == ["utilisateurs.change_utilisateur"]
        assert "workspace_link" not in self.user.attributs_acces
        assert self.user.workspace_link["user"] == 999
        assert self.user.workspace_link["version"] == self.client.get(WORKSPACE).data["version"]
        assert not self.user.get_all_permissions()
        assert self.client.put(LINK, {"peer": None, "user": None}, format="json").status_code == 200
        self.user.refresh_from_db()
        assert self.user.workspace_link is None

    def test_arbitrary_peers_fields_and_accounts_outside_tenant_are_rejected(self):
        self.login(self.user)
        assert self.client.put(LINK, {"peer": self.peer, "user": 1}, format="json").status_code == 403
        assert self.client.put(LINK, {"peer": None, "user": 1}, format="json").status_code == 400
        assert (
            self.client.put(LINK, {"peer": None, "user": None, "is_superuser": True}, format="json").status_code == 400
        )
        self.user.etablissement = None
        self.user.save()
        assert self.client.get(WORKSPACE).status_code == 403
        assert self.client.put(LINK, {"peer": None, "user": None}, format="json").status_code == 403
