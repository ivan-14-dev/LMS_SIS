"""Tenant-schema group authoring and assignment regressions."""

from unittest.mock import patch

from apps.core.models import WorkflowEvent
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.utilisateurs.models import Utilisateur
from django.conf import settings
from django.contrib.auth.models import Group, Permission
from django.db import connection
from django.test import override_settings
from django_tenants.utils import get_tenant_domain_model, schema_context
from rest_framework.test import APIClient

from sis_common.workflow_tracking import record_workflow_event

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

    def _batch_events(self, group):
        return WorkflowEvent.objects.filter(app_label="auth", model="group", object_id=str(group.pk))

    def _assert_batch_denied(self, group, payload, expected_status):
        for action in ("assign_many", "unassign_many"):
            with self.subTest(action=action, payload=payload):
                if action == "unassign_many":
                    self.student.groups.add(group)
                else:
                    self.student.groups.remove(group)
                members = set(group.user_set.values_list("pk", flat=True))
                event_count = self._batch_events(group).count()
                response = self.client.post(f"{BASE}groupes/{group.pk}/{action}/", payload, format="json")
                assert response.status_code == expected_status, response.data
                assert set(group.user_set.values_list("pk", flat=True)) == members
                assert self._batch_events(group).count() == event_count

    def test_batch_membership_replay_and_named_audit(self):
        peer = Utilisateur.objects.create_user("batch-peer", role=self.student.role, etablissement=self.tenant)
        group = Group.objects.create(name="batch-readers")
        group.permissions.add(self.grant)
        other = Group.objects.create(name="untouched-group")
        other.user_set.add(self.student, peer)
        self.student.groups.add(group)
        self.admin.user_permissions.remove(Permission.objects.get(content_type__app_label="auth", codename="add_group"))
        self.client.force_authenticate(Utilisateur.objects.get(pk=self.admin.pk))
        ids = sorted([peer.pk, self.student.pk])
        cases = (
            ("assign_many", "added_user_ids", [peer.pk], ids),
            ("assign_many", "added_user_ids", [], ids),
            ("unassign_many", "removed_user_ids", ids, []),
            ("unassign_many", "removed_user_ids", [], []),
        )
        for index, (action, change_key, changed, members) in enumerate(cases, start=1):
            with self.subTest(action=action, replay=index % 2 == 0):
                response = self.client.post(
                    f"{BASE}groupes/{group.pk}/{action}/", {"user_ids": list(reversed(ids))}, format="json"
                )
                assert response.status_code == 200, response.data
                assert response.data == {"group_id": group.pk, "user_ids": ids}
                assert list(group.user_set.order_by("pk").values_list("pk", flat=True)) == members
                assert list(other.user_set.order_by("pk").values_list("pk", flat=True)) == ids
                events = self._batch_events(group)
                assert events.count() == index
                event = events.latest("pk")
                assert event.actor_id == self.admin.pk
                assert event.tenant_id == self.tenant.pk
                assert event.action == action
                assert event.metadata == {"group_id": group.pk, "user_ids": ids, change_key: changed}

    def test_batch_invalid_target_rolls_back_whole_batch(self):
        foreign = type(self.tenant)(schema_name="batch_foreign")
        self.setup_tenant(foreign)
        foreign.auto_create_schema = False
        with schema_context("public"):
            foreign.save()
        outsider = Utilisateur.objects.create_user("batch-outsider", etablissement=foreign)
        root = Utilisateur.objects.create_superuser("batch-protected-root", etablissement=self.tenant)
        group = Group.objects.create(name="batch-local")
        for target, expected_status in (
            (outsider.pk, 404),
            (root.pk + 100000, 404),
            (self.admin.pk, 403),
            (root.pk, 403),
        ):
            self._assert_batch_denied(group, {"user_ids": [self.student.pk, target]}, expected_status)

    def test_batch_requires_each_unscoped_permission(self):
        group = Group.objects.create(name="batch-permissions")
        for app_label, codename in (
            ("auth", "change_group"),
            ("utilisateurs", "change_utilisateur"),
            ("utilisateurs", "view_utilisateur"),
        ):
            permission = Permission.objects.get(content_type__app_label=app_label, codename=codename)
            for mode in ("missing", "scoped", "empty_scope"):
                with self.subTest(permission=codename, mode=mode):
                    self.admin.attributs_acces = {}
                    if mode == "missing":
                        self.admin.user_permissions.remove(permission)
                    else:
                        self.admin.attributs_acces = {
                            "permission_scopes": {
                                f"{app_label}.{codename}": {"classes": [1]} if mode == "scoped" else {}
                            }
                        }
                    self.admin.save(update_fields=["attributs_acces"])
                    self.client.force_authenticate(Utilisateur.objects.get(pk=self.admin.pk))
                    self._assert_batch_denied(group, {"user_ids": [self.student.pk]}, 403)
                    self.admin.user_permissions.add(permission)

    def test_batch_preserves_actor_and_group_guards(self):
        foreign = type(self.tenant)(schema_name="batch_actor_foreign")
        self.setup_tenant(foreign)
        foreign.auto_create_schema = False
        with schema_context("public"):
            foreign.save()
        outsider = Utilisateur.objects.create_superuser("batch-foreign-actor", etablissement=foreign)
        inactive_root = Utilisateur.objects.create_superuser(
            "batch-inactive-root", etablissement=self.tenant, is_active=False
        )
        group = Group.objects.create(name="batch-protected-group")
        self.admin.is_active = False
        self.admin.save(update_fields=["is_active"])
        for actor in (outsider, self.admin, inactive_root):
            with self.subTest(actor=actor.username):
                self.client.force_authenticate(actor)
                self._assert_batch_denied(group, {"user_ids": [self.student.pk]}, 403)
        self.admin.is_active = True
        self.admin.save(update_fields=["is_active"])
        self.client.force_authenticate(Utilisateur.objects.get(pk=self.admin.pk))
        self.admin.groups.add(group)
        self._assert_batch_denied(group, {"user_ids": [self.student.pk]}, 403)
        self.admin.groups.remove(group)
        group.permissions.add(self.forbidden)
        self._assert_batch_denied(group, {"user_ids": [self.student.pk]}, 403)
        group.permissions.set(Permission.objects.filter(content_type__app_label="auth", codename="view_group"))
        self.admin.attributs_acces = {"permission_scopes": {"auth.view_group": {"classes": [1]}}}
        self.admin.save(update_fields=["attributs_acces"])
        self.client.force_authenticate(Utilisateur.objects.get(pk=self.admin.pk))
        self._assert_batch_denied(group, {"user_ids": [self.student.pk]}, 403)

    def test_batch_rejects_malformed_lists_without_coercion(self):
        group = Group.objects.create(name="batch-validation")
        invalid_lists = (
            [],
            list(range(1, 102)),
            [self.student.pk, self.student.pk],
            None,
            str(self.student.pk),
            {"id": self.student.pk},
            *([self.student.pk, value] for value in (True, False, 0, -1, "1", 1.0, 1.5, None, [], {})),
        )
        for payload in ({}, [], *({"user_ids": values} for values in invalid_lists)):
            self._assert_batch_denied(group, payload, 400)

    def test_batch_accepts_one_and_one_hundred_accounts(self):
        users = Utilisateur.objects.bulk_create(
            [Utilisateur(username=f"batch-limit-{index}", etablissement=self.tenant) for index in range(99)]
        )
        group = Group.objects.create(name="batch-limits")
        for ids in ([self.student.pk], sorted([self.student.pk, *(user.pk for user in users)])):
            for action in ("assign_many", "unassign_many"):
                with self.subTest(size=len(ids), action=action):
                    response = self.client.post(
                        f"{BASE}groupes/{group.pk}/{action}/", {"user_ids": list(reversed(ids))}, format="json"
                    )
                    assert response.status_code == 200, response.data
                    assert response.data == {"group_id": group.pk, "user_ids": ids}
                    assert group.user_set.count() == (len(ids) if action == "assign_many" else 0)

    def test_batch_audit_failure_rolls_back_memberships_and_event(self):
        group = Group.objects.create(name="batch-audit-atomic")

        def failing_audit(*args, **kwargs):
            record_workflow_event(*args, **kwargs)
            raise RuntimeError("audit failure")

        for action in ("assign_many", "unassign_many"):
            if action == "unassign_many":
                self.student.groups.add(group)
            before = list(group.user_set.values_list("pk", flat=True))
            with patch("sis_common.group_assignment.record_workflow_event", side_effect=failing_audit):
                with self.assertRaisesMessage(RuntimeError, "audit failure"):
                    self.client.post(
                        f"{BASE}groupes/{group.pk}/{action}/", {"user_ids": [self.student.pk]}, format="json"
                    )
            assert list(group.user_set.values_list("pk", flat=True)) == before
            assert not self._batch_events(group).exists()

    def test_batch_tenant_superuser_retains_existing_exception(self):
        root = Utilisateur.objects.create_superuser("batch-root", etablissement=self.tenant)
        group = Group.objects.create(name="batch-root-group")
        group.permissions.add(self.forbidden)
        root.groups.add(group)
        self.client.force_authenticate(root)
        ids = sorted([root.pk, self.student.pk])
        for action in ("assign_many", "unassign_many"):
            response = self.client.post(f"{BASE}groupes/{group.pk}/{action}/", {"user_ids": ids}, format="json")
            assert response.status_code == 200, response.data
            assert response.data == {"group_id": group.pk, "user_ids": ids}
            assert group.user_set.count() == (2 if action == "assign_many" else 0)

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
