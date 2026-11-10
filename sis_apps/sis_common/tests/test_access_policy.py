from types import SimpleNamespace

from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.utilisateurs.models import Utilisateur
from asgiref.sync import async_to_sync
from django.apps import apps
from django.conf import settings
from django.contrib.auth.models import Group, Permission
from guardian.shortcuts import assign_perm
from rest_framework.authtoken.models import Token

from sis_common.authorization import has_business_permission_or_role, request_has_role_or_business_access
from sis_common.group_backends import ActiveGroupModelBackend


class AccountAccessTests(TenantAPITestCase):
    def setUp(self):
        self.root = Utilisateur.objects.create_superuser("access-admin", etablissement=self.tenant)
        self.user = Utilisateur.objects.create_user("access-learner", etablissement=self.tenant)
        self.permission = Permission.objects.get(content_type__app_label="auth", codename="view_group")
        self.url = f"/api/v1/utilisateurs/comptes/{self.user.pk}/access-policy/"
        self.authenticate(self.root)

    def authenticate(self, user):
        token, _ = Token.objects.get_or_create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def payload(self, **changes):
        response = self.client.get(self.url)
        assert response.status_code == 200, response.data
        payload = {
            key: response.data[key]
            for key in ("version", "additional_roles", "user_permissions", "denied_permissions", "disabled_features")
        }
        return {**payload, **changes}

    def test_denial_overrides_direct_group_object_and_legacy_role_grants(self):
        group = Group.objects.create(name="access-grant")
        group.permissions.add(self.permission)
        self.user.groups.add(group)
        assign_perm(self.permission, self.user, group)
        data = self.payload(user_permissions=[self.permission.pk], denied_permissions=["auth.view_group"])
        response = self.client.put(self.url, data, format="json")
        assert response.status_code == 200, response.data
        user = Utilisateur.objects.get(pk=self.user.pk)
        assert not user.has_perm("auth.view_group")
        assert not user.has_perm("auth.view_group", group)
        assert not async_to_sync(user.ahas_perm)("auth.view_group")
        assert not has_business_permission_or_role(user, "auth.view_group", [user.role])
        assert not request_has_role_or_business_access(
            SimpleNamespace(user=user, tenant=self.tenant), "auth.view_group", [user.role]
        )
        assert not ActiveGroupModelBackend().with_perm("auth.view_group").filter(pk=user.pk).exists()
        assert "auth.view_group" not in response.data["effective_permissions"]
        assert group.permissions.filter(pk=self.permission.pk).exists()
        assert user.user_permissions.filter(pk=self.permission.pk).exists()
        self.authenticate(user)
        assert self.client.get("/api/v1/utilisateurs/groupes/").status_code == 403
        self.authenticate(self.root)
        assert self.client.put(self.url, self.payload(denied_permissions=[]), format="json").status_code == 200
        self.authenticate(user)
        assert self.client.get("/api/v1/utilisateurs/groupes/").status_code == 200

    def test_permission_sources_keep_inactive_groups_and_denials_visible_without_granting_them(self):
        group = Group.objects.create(name="Recorded readers")
        group.permissions.add(self.permission)
        self.user.groups.add(group)
        apps.get_model("utilisateurs", "GroupLifecycle").objects.create(group=group, actif=False)
        self.user.attributs_acces = {
            "permission_scopes": {"auth.view_group": {"classes": [3]}},
            "access_policy": {
                "denied_permissions": ["auth.view_group"],
                "additional_roles": ["parent"],
            },
        }
        self.user.save()
        response = self.client.get(self.url)
        assert response.status_code == 200
        assert response.data["permission_groups"] == [
            {
                "id": group.pk,
                "name": group.name,
                "active": False,
                "permissions": ["auth.view_group"],
            }
        ]
        assert response.data["permission_scopes"] == {"auth.view_group": {"classes": [3]}}
        assert "auth.view_group" not in response.data["effective_permissions"]
        response = self.client.get("/api/v1/utilisateurs/comptes/")
        users = response.data["results"] if isinstance(response.data, dict) else response.data
        target = next(user for user in users if user["id"] == self.user.pk)
        assert {role["code"] for role in target["roles"]} == {self.user.role, "parent"}

    def test_disabled_superuser_has_no_usable_permissions_in_the_read_only_summary(self):
        target = Utilisateur.objects.create_superuser(
            "inactive-access-admin", etablissement=self.tenant, is_active=False
        )
        response = self.client.get(f"/api/v1/utilisateurs/comptes/{target.pk}/access-policy/")
        assert response.status_code == 200
        assert response.data["is_active"] is False
        assert response.data["effective_permissions"] == []

    def test_roles_are_explicit_request_local_and_never_saved_as_primary(self):
        primary = self.user.role
        response = self.client.put(self.url, self.payload(additional_roles=["parent"]), format="json")
        assert response.status_code == 200, response.data
        self.authenticate(self.user)
        url = "/api/v1/utilisateurs/comptes/"
        response = self.client.get(f"{url}capabilities/", HTTP_X_SIS_ROLE="parent")
        assert response.status_code == 200, response.data
        assert response.data["role"] == "parent"
        assert response.data["primary_role"] == primary
        assert {role["code"] for role in response.data["roles"]} == {primary, "parent"}
        assert not response.data["portals"]["staff"]
        assert not response.data["portals"]["parent"]
        response = self.client.patch(
            f"{url}update_profile/", {"first_name": "Updated"}, format="json", HTTP_X_SIS_ROLE="parent"
        )
        assert response.status_code == 200, response.data
        self.user.refresh_from_db()
        assert self.user.role == primary
        assert self.user.first_name == "Updated"
        assert self.client.get(f"{url}capabilities/").data["role"] == primary
        assert self.client.get(f"{url}capabilities/", HTTP_X_SIS_ROLE="enseignant").status_code == 403

    def test_student_feature_denial_is_enforced_on_direct_api_requests(self):
        response = self.client.put(
            self.url, self.payload(disabled_features=["timetable", "lms", "library"]), format="json"
        )
        assert response.status_code == 200, response.data
        self.authenticate(self.user)
        for path in ("portail/apprenant/emploi_du_temps/", "integration/my-learning/", "edt/", "bibliotheque/"):
            response = self.client.get(f"/api/v1/{path}")
            assert response.status_code == 403, (path, response.data)
        response = self.client.get("/api/v1/utilisateurs/comptes/capabilities/")
        assert response.status_code == 200
        assert "mon-emploi-du-temps" in response.data["disabled_paths"]

    def test_denied_model_permission_cannot_be_bypassed_by_a_read_only_route(self):
        response = self.client.put(
            self.url, self.payload(denied_permissions=["utilisateurs.view_utilisateur"]), format="json"
        )
        assert response.status_code == 200
        self.authenticate(self.user)
        assert self.client.get("/api/v1/utilisateurs/comptes/").status_code == 403
        assert self.client.get("/api/v1/utilisateurs/comptes/me/").status_code == 200
        assert self.client.get("/api/v1/auth/session/", HTTP_X_SIS_ROLE="retired-role").status_code == 200

    def test_assigned_teacher_is_selectable_without_changing_primary_learner_role(self):
        response = self.client.put(self.url, self.payload(additional_roles=["enseignant"]), format="json")
        assert response.status_code == 200, response.data
        model = apps.get_model("classes.Classe" if settings.SIS_VARIANT == "secondaire" else "notes.Evaluation")
        field = model._meta.get_field("prof_principal" if settings.SIS_VARIANT == "secondaire" else "enseignant")
        assert Utilisateur.objects.filter(field.get_limit_choices_to(), pk=self.user.pk).exists()
        assert self.client.put(self.url, self.payload(additional_roles=[]), format="json").status_code == 200
        assert not Utilisateur.objects.filter(field.get_limit_choices_to(), pk=self.user.pk).exists()

    def test_denied_results_cannot_leak_through_an_aggregate_personal_portal(self):
        response = self.client.put(self.url, self.payload(denied_permissions=["notes.view_note"]), format="json")
        assert response.status_code == 200
        assert response.data["disabled_features"] == []
        self.authenticate(self.user)
        assert self.client.get("/api/v1/portail/apprenant/tableau_bord/").status_code == 403
        response = self.client.get("/api/v1/utilisateurs/comptes/capabilities/")
        assert "learner_portal" in response.data["disabled_features"]

    def test_stale_writes_unknown_rights_self_and_superuser_changes_are_refused(self):
        data = self.payload(additional_roles=["parent"])
        assert self.client.put(self.url, data, format="json").status_code == 200
        assert self.client.put(self.url, {**data, "additional_roles": []}, format="json").status_code == 409
        for changes in (
            {"additional_roles": ["super_admin"]},
            {"additional_roles": ["invented"]},
            {"denied_permissions": ["invented.permission"]},
            {"disabled_features": ["invented"]},
            {"unrecognized": True},
        ):
            assert self.client.put(self.url, self.payload(**changes), format="json").status_code == 400
        own_url = f"/api/v1/utilisateurs/comptes/{self.root.pk}/access-policy/"
        assert not self.client.get(own_url).data["editable"]
        assert self.client.put(own_url, data, format="json").status_code == 403
        self.authenticate(self.user)
        assert self.client.put(self.url, data, format="json").status_code == 403

    def test_delegation_cannot_restore_an_unowned_permission_or_add_a_business_role(self):
        manager = Utilisateur.objects.create_user("access-manager", etablissement=self.tenant)
        manager.user_permissions.set(
            Permission.objects.filter(
                codename__in=["view_utilisateur", "change_utilisateur", "change_group", "view_group"]
            )
        )
        initial = self.payload(denied_permissions=["auth.delete_group"], disabled_features=["studio"])
        assert self.client.put(self.url, initial, format="json").status_code == 200
        self.authenticate(manager)
        assert self.client.put(self.url, self.payload(denied_permissions=[]), format="json").status_code == 403
        assert self.client.put(self.url, self.payload(disabled_features=[]), format="json").status_code == 403
        assert (
            self.client.put(self.url, self.payload(additional_roles=["enseignant"]), format="json").status_code == 403
        )
        assert (
            self.client.put(self.url, self.payload(user_permissions=[self.permission.pk]), format="json").status_code
            == 200
        )

    def test_tenant_boundary_attributes_and_role_revocation_are_preserved(self):
        self.user.attributs_acces = {"cohort": "existing"}
        self.user.save(update_fields=["attributs_acces"])
        assert self.client.put(self.url, self.payload(additional_roles=["parent"]), format="json").status_code == 200
        self.user.refresh_from_db()
        assert self.user.attributs_acces["cohort"] == "existing"
        assert self.client.put(self.url, self.payload(additional_roles=[]), format="json").status_code == 200
        self.authenticate(self.user)
        assert (
            self.client.get("/api/v1/utilisateurs/comptes/capabilities/", HTTP_X_SIS_ROLE="parent").status_code == 403
        )
        self.authenticate(self.root)
        self.user.etablissement = None
        self.user.save(update_fields=["etablissement"])
        assert self.client.get(self.url).status_code == 404
