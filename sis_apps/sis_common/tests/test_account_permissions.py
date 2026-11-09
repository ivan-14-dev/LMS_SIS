"""Both account APIs distinguish institutional labels from delegated rights."""

from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.utilisateurs.models import GroupLifecycle, Utilisateur
from django.conf import settings
from django.contrib.auth.models import Group, Permission


class ExplicitAccountPermissionTests(TenantAPITestCase):
    def setUp(self):
        self.manager = Utilisateur.objects.create_user(
            "account-manager",
            role="direction" if settings.SIS_VARIANT == "secondaire" else "doyen",
            is_staff=True,
            etablissement=self.tenant,
        )
        self.target = Utilisateur.objects.create_user("account-target", etablissement=self.tenant)
        self.url = f"/api/v1/utilisateurs/comptes/{self.target.pk}/"
        self.client.force_authenticate(self.manager)

    def test_role_staff_and_configured_group_do_not_grant_account_administration(self):
        self.tenant.configuration_academique = {
            "permission_groups": [
                {
                    "code": f"academic_admin_{'secondary' if settings.SIS_VARIANT == 'secondaire' else 'superieur'}",
                    "permissions": [],
                    "attributes": {},
                }
            ],
        }
        self.tenant.save(update_fields=["configuration_academique"])
        response = self.client.get("/api/v1/utilisateurs/comptes/")
        assert response.status_code == 200
        assert [user["id"] for user in response.data["results"]] == [self.manager.pk]
        assert self.client.get(self.url).status_code == 404
        assert self.client.patch(self.url, {"first_name": "Denied"}, format="json").status_code == 403
        assert self.client.post(f"{self.url}force_logout/").status_code == 403
        assert self.client.get("/api/v1/utilisateurs/comptes/me/").status_code == 200
        assert (
            self.client.patch(
                "/api/v1/utilisateurs/comptes/update_profile/",
                {"first_name": "Self"},
                format="json",
            ).status_code
            == 200
        )

    def test_group_assignment_and_deactivation_control_directory_and_update(self):
        group = Group.objects.create(name="Local account managers")
        lifecycle = GroupLifecycle.objects.create(group=group)
        group.permissions.set(
            Permission.objects.filter(
                content_type__app_label="utilisateurs",
                codename__in=["view_utilisateur", "change_utilisateur"],
            )
        )
        self.manager.groups.add(group)
        assert self.client.get(self.url).status_code == 200
        assert self.client.patch(self.url, {"first_name": "Allowed"}, format="json").status_code == 200
        lifecycle.actif = False
        lifecycle.save(update_fields=["actif"])
        self.client.force_authenticate(Utilisateur.objects.get(pk=self.manager.pk))
        assert self.client.get(self.url).status_code == 404
        assert self.client.patch(self.url, {"first_name": "Denied"}, format="json").status_code == 403
        self.target.refresh_from_db()
        assert self.target.first_name == "Allowed"

    def test_scoped_permission_cannot_be_used_as_an_unrestricted_account_grant(self):
        self.manager.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label="utilisateurs",
                codename__in=["view_utilisateur", "change_utilisateur"],
            )
        )
        self.manager.attributs_acces = {
            "permission_scopes": {
                "utilisateurs.view_utilisateur": {"comptes": [self.target.pk]},
                "utilisateurs.change_utilisateur": {"comptes": [self.target.pk]},
            },
        }
        self.manager.save(update_fields=["attributs_acces"])
        assert self.client.get(self.url).status_code == 404
        assert self.client.patch(self.url, {"first_name": "Denied"}, format="json").status_code == 403
