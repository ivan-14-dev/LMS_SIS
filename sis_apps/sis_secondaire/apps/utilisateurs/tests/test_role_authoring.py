"""Tenant-schema group authoring and assignment regressions."""

from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.utilisateurs.models import Utilisateur
from django.conf import settings
from django.contrib.auth.models import Group, Permission
from django.db import connection
from django.test import override_settings
from django_tenants.utils import get_tenant_domain_model, schema_context
from rest_framework.test import APIClient

BASE = "/api/v1/utilisateurs/"


class SecureAPIClient(APIClient):
    def generic(self, method, path, *args, **kwargs):
        return super().generic(method, path, *args, secure=True, **kwargs)


class GroupAuthoringTests(TenantAPITestCase):
    client_class = SecureAPIClient

    def setUp(self):
        self.admin = Utilisateur.objects.create_user("group-admin", role="direction", etablissement=self.tenant)
        self.student = Utilisateur.objects.create_user("group-student", role="eleve", etablissement=self.tenant)
        self.grant = Permission.objects.get(content_type__app_label="utilisateurs", codename="view_utilisateur")
        self.forbidden = Permission.objects.get(content_type__app_label="auth", codename="add_permission")
        self.admin.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label="auth", codename__in=["add_group", "change_group", "view_group"]
            ),
            Permission.objects.get(content_type__app_label="utilisateurs", codename="change_utilisateur"),
            self.grant,
        )
        self.client.force_authenticate(self.admin)

    def test_admin_authors_and_assigns_only_own_permissions(self):
        response = self.client.post(
            f"{BASE}groupes/", {"name": "local-academic-readers", "permissions": [self.grant.pk]}, format="json"
        )
        assert response.status_code == 201, response.data
        group = Group.objects.get(pk=response.data["id"])
        assert list(group.permissions.values_list("pk", flat=True)) == [self.grant.pk]
        assert self.grant.pk in [row["id"] for row in self.client.get(f"{BASE}permissions/").data["results"]]
        response = self.client.patch(f"{BASE}groupes/{group.pk}/", {"name": "local-readers"}, format="json")
        assert response.status_code == 200, response.data
        response = self.client.post(f"{BASE}groupes/{group.pk}/assign/", {"user_id": self.student.pk})
        assert response.status_code == 200, response.data
        self.student.refresh_from_db()
        assert self.student.groups.filter(pk=group.pk).exists()
        assert Utilisateur.objects.get(pk=self.student.pk).has_perm("utilisateurs.view_utilisateur")
        response = self.client.post(f"{BASE}groupes/{group.pk}/unassign/", {"user_id": self.student.pk})
        assert response.status_code == 200, response.data
        assert not self.student.groups.filter(pk=group.pk).exists()
        assert not Utilisateur.objects.get(pk=self.student.pk).has_perm("utilisateurs.view_utilisateur")

    def test_out_of_scope_and_scoped_permissions_cannot_be_delegated(self):
        response = self.client.post(
            f"{BASE}groupes/", {"name": "forbidden-grant", "permissions": [self.forbidden.pk]}, format="json"
        )
        assert response.status_code == 400, response.data
        assert not Group.objects.filter(name="forbidden-grant").exists()
        group = Group.objects.create(name="existing-group")
        response = self.client.patch(
            f"{BASE}groupes/{group.pk}/", {"permissions": [self.forbidden.pk]}, format="json"
        )
        assert response.status_code == 400, response.data
        group.permissions.add(self.forbidden)
        assert self.client.post(f"{BASE}groupes/{group.pk}/assign/", {"user_id": self.student.pk}).status_code == 403
        assert not self.student.groups.filter(pk=group.pk).exists()
        self.admin.attributs_acces = {
            "permission_scopes": {"utilisateurs.view_utilisateur": {"classes": [1]}}
        }
        self.admin.save(update_fields=["attributs_acces"])
        response = self.client.post(
            f"{BASE}groupes/", {"name": "scoped-grant", "permissions": [self.grant.pk]}, format="json"
        )
        assert response.status_code == 400, response.data

    def test_self_promotion_and_direct_account_bypasses_are_denied(self):
        group = Group.objects.create(name="self-target")
        group.permissions.add(self.grant)
        assert self.client.post(f"{BASE}groupes/{group.pk}/assign/", {"user_id": self.admin.pk}).status_code == 403
        self.admin.groups.add(group)
        assert self.client.patch(f"{BASE}groupes/{group.pk}/", {"name": "self-edited"}).status_code == 403
        for payload in (
            {"groups": [group.pk]},
            {"user_permissions": [self.forbidden.pk]},
            {"attributs_acces": {}},
            {"role": "super_admin"},
        ):
            response = self.client.patch(f"{BASE}comptes/{self.admin.pk}/", payload, format="json")
            assert response.status_code == 400, response.data
        response = self.client.patch(
            f"{BASE}comptes/{self.student.pk}/", {"role": "direction"}, format="json"
        )
        assert response.status_code == 400, response.data
        response = self.client.patch(
            f"{BASE}comptes/{self.student.pk}/", {"groups": [group.pk]}, format="json"
        )
        assert response.status_code == 400, response.data
        self.student.refresh_from_db()
        assert self.student.role == "eleve"
        assert not self.student.groups.exists()

    def test_foreign_institution_account_and_assignment_are_denied(self):
        foreign = type(self.tenant)(schema_name="group_author_foreign")
        self.setup_tenant(foreign)
        foreign.auto_create_schema = False
        with schema_context("public"):
            foreign.save()
        outsider = Utilisateur.objects.create_user(
            "foreign-author", role="direction", etablissement=foreign, is_superuser=True
        )
        target = Utilisateur.objects.create_user("foreign-target", role="eleve", etablissement=foreign)
        group = Group.objects.create(name="local-only")
        assert self.client.post(f"{BASE}groupes/{group.pk}/assign/", {"user_id": target.pk}).status_code == 404
        self.client.force_authenticate(outsider)
        assert self.client.post(f"{BASE}groupes/", {"name": "foreign-write"}).status_code == 403
        assert self.client.get(f"{BASE}groupes/").status_code == 403
        assert not Group.objects.filter(name="foreign-write").exists()

    def test_unprivileged_user_cannot_create_or_assign_groups(self):
        group = Group.objects.create(name="admin-only")
        self.client.force_authenticate(self.student)
        assert self.client.post(f"{BASE}groupes/", {"name": "not-allowed"}).status_code == 403
        assert self.client.post(f"{BASE}groupes/{group.pk}/assign/", {"user_id": self.admin.pk}).status_code == 403

    def test_tenant_superuser_retains_full_group_administration(self):
        root = Utilisateur.objects.create_superuser(
            "root-group-author", role="super_admin"
        )
        self.client.force_authenticate(root)
        response = self.client.post(
            f"{BASE}groupes/", {"name": "root-managed", "permissions": [self.forbidden.pk]}, format="json"
        )
        assert response.status_code == 201, response.data
        group_id = response.data["id"]
        response = self.client.post(f"{BASE}groupes/{group_id}/assign/", {"user_id": self.student.pk})
        assert response.status_code == 200, response.data
        assert self.student.groups.filter(pk=group_id).exists()
        assert self.client.delete(f"{BASE}groupes/{group_id}/").status_code == 204


class GroupSchemaIsolationTests(TenantAPITestCase):
    client_class = SecureAPIClient
    domain = "group-author-secondary.example.test"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with schema_context("public"):
            cls.peer = type(cls.tenant)(schema_name="group_author_secondary_peer")
            cls.setup_tenant(cls.peer)
            cls.peer.save(verbosity=0)
            get_tenant_domain_model().objects.create(tenant=cls.peer, domain=cls.domain)

    @classmethod
    def tearDownClass(cls):
        try:
            with schema_context("public"):
                cls.peer._drop_schema(force_drop=True)
                # The ORM collector would query tenant-only tables in public.
                get_tenant_domain_model().objects.filter(tenant=cls.peer)._raw_delete(connection.alias)
                type(cls.peer).objects.filter(pk=cls.peer.pk)._raw_delete(connection.alias)
        finally:
            super().tearDownClass()

    def test_groups_are_isolated_between_real_tenant_schemas(self):
        Group.objects.create(name="only-in-primary")
        with schema_context(self.peer.schema_name):
            peer_admin = Utilisateur.objects.create_superuser(
                "peer-group-admin", role="super_admin", etablissement=self.peer
            )
            Group.objects.create(name="only-in-peer")
        with override_settings(ALLOWED_HOSTS=[*settings.ALLOWED_HOSTS, self.domain]):
            client = APIClient(SERVER_NAME=self.domain)
            client.force_authenticate(peer_admin)
            response = client.get(f"{BASE}groupes/", secure=True)
            assert response.status_code == 200, response.data
            names = {item["name"] for item in response.data["results"]}
            assert "only-in-peer" in names
            assert "only-in-primary" not in names
        connection.set_tenant(self.tenant)
        admin = Utilisateur.objects.create_superuser(
            "primary-group-admin", role="super_admin", etablissement=self.tenant
        )
        self.client.force_authenticate(admin)
        response = self.client.get(f"{BASE}groupes/")
        assert response.status_code == 200, response.data
        names = {item["name"] for item in response.data["results"]}
        assert "only-in-primary" in names
        assert "only-in-peer" not in names
