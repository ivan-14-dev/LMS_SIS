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
        self.admin = Utilisateur.objects.create_user("group-admin", role="doyen", etablissement=self.tenant)
        self.student = Utilisateur.objects.create_user("group-student", role="etudiant", etablissement=self.tenant)
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

    def test_group_lifecycle_and_single_assignment_named_audit(self):
        self.admin.user_permissions.add(Permission.objects.get(content_type__app_label="auth", codename="delete_group"))
        change_user = Permission.objects.get(content_type__app_label="utilisateurs", codename="change_utilisateur")
        view_group = Permission.objects.get(content_type__app_label="auth", codename="view_group")
        before = {
            "name": "local-academic-readers",
            "permissions": sorted(
                [
                    {"id": self.grant.pk, "code": "utilisateurs.view_utilisateur"},
                    {"id": change_user.pk, "code": "utilisateurs.change_utilisateur"},
                ],
                key=lambda item: item["id"],
            ),
        }
        after = {
            "name": "local-readers",
            "permissions": sorted(
                [
                    {"id": self.grant.pk, "code": "utilisateurs.view_utilisateur"},
                    {"id": view_group.pk, "code": "auth.view_group"},
                ],
                key=lambda item: item["id"],
            ),
        }
        headers = {"HTTP_X_REQUEST_ID": "group-lifecycle-audit"}
        response = self.client.post(
            f"{BASE}groupes/",
            {"name": before["name"], "permissions": [self.grant.pk, change_user.pk]},
            format="json",
            **headers,
        )
        assert response.status_code == 201, response.data
        group = Group.objects.get(pk=response.data["id"])
        group_id = group.pk
        assert list(group.permissions.order_by("pk").values_list("pk", flat=True)) == [
            item["id"] for item in before["permissions"]
        ]
        assert self.grant.pk in [row["id"] for row in self.client.get(f"{BASE}permissions/").data["results"]]
        expected = [("group_created", {"group_id": group_id, "before": None, "after": before})]
        response = self.client.patch(
            f"{BASE}groupes/{group_id}/",
            {"name": after["name"], "permissions": [self.grant.pk, view_group.pk]},
            format="json",
            **headers,
        )
        assert response.status_code == 200, response.data
        group.refresh_from_db()
        assert group.name == after["name"]
        assert list(group.permissions.order_by("pk").values_list("pk", flat=True)) == [
            item["id"] for item in after["permissions"]
        ]
        expected.append(("group_updated", {"group_id": group_id, "before": before, "after": after}))
        other = Group.objects.create(name="untouched-single-group")
        self.student.groups.add(other)
        for action, change_key, changed, members in (
            ("assign", "added_user_ids", [self.student.pk], [self.student.pk]),
            ("assign", "added_user_ids", [], [self.student.pk]),
            ("unassign", "removed_user_ids", [self.student.pk], []),
            ("unassign", "removed_user_ids", [], []),
        ):
            with self.subTest(action=action, replay=not changed):
                response = self.client.post(
                    f"{BASE}groupes/{group_id}/{action}/", {"user_id": self.student.pk}, format="json", **headers
                )
                assert response.status_code == 200, response.data
                assert response.data == {"user_id": self.student.pk, "group_id": group_id}
                assert list(group.user_set.values_list("pk", flat=True)) == members
                assert list(other.user_set.values_list("pk", flat=True)) == [self.student.pk]
                assert Utilisateur.objects.get(pk=self.student.pk).has_perm("utilisateurs.view_utilisateur") == bool(
                    members
                )
                expected.append(
                    (
                        action,
                        {
                            "group_id": group_id,
                            "user_id": self.student.pk,
                            "before": after,
                            "after": after,
                            change_key: changed,
                        },
                    )
                )
        assert self.client.delete(f"{BASE}groupes/{group_id}/", **headers).status_code == 204
        assert not Group.objects.filter(pk=group_id).exists()
        assert self.student.groups.filter(pk=other.pk).exists()
        expected.append(("group_deleted", {"group_id": group_id, "before": after, "after": None}))
        events = list(self._batch_events(group).order_by("pk"))
        assert len(events) == len(expected)
        for event, (action, metadata) in zip(events, expected):
            with self.subTest(action=action, event=event.pk):
                assert event.action == action
                assert event.actor_id == self.admin.pk
                assert event.tenant_id == self.tenant.pk
                assert event.request_id == headers["HTTP_X_REQUEST_ID"]
                assert event.object_id == str(group_id)
                assert event.object_repr == (metadata["after"] or metadata["before"])["name"]
                assert event.metadata == metadata

    def test_single_operation_audit_failure_rolls_back_mutation_and_event(self):
        self.admin.user_permissions.add(Permission.objects.get(content_type__app_label="auth", codename="delete_group"))
        replacement = Permission.objects.get(content_type__app_label="auth", codename="view_group")
        for operation in ("create", "update", "partial_update", "delete", "assign", "unassign"):
            with self.subTest(operation=operation):
                group = Group.objects.create(name=f"audit-atomic-{operation}")
                group.permissions.add(self.grant)
                if operation not in ("create", "assign"):
                    self.student.groups.add(group)
                before_members = list(group.user_set.values_list("pk", flat=True))
                before_ids = set(Group.objects.values_list("pk", flat=True))
                event_count = WorkflowEvent.objects.count()
                name = group.name
                payload = {
                    "name": f"{name}-edited",
                    "permissions": [self.grant.pk if operation == "create" else replacement.pk],
                }
                method = {"create": "post", "update": "put", "partial_update": "patch", "delete": "delete"}.get(
                    operation, "post"
                )
                url = f"{BASE}groupes/" if operation == "create" else f"{BASE}groupes/{group.pk}/"
                if operation in ("assign", "unassign"):
                    url += f"{operation}/"
                    payload = {"user_id": self.student.pk}

                def failing_audit(request, instance, *args, **kwargs):
                    if operation == "delete":
                        assert not Group.objects.filter(pk=group.pk).exists()
                        assert not self.student.groups.filter(pk=group.pk).exists()
                    elif operation in ("create", "update", "partial_update"):
                        saved = Group.objects.get(pk=instance.pk)
                        assert saved.name == payload["name"]
                        assert list(saved.permissions.values_list("pk", flat=True)) == payload["permissions"]
                    else:
                        assert self.student.groups.filter(pk=group.pk).exists() == (operation == "assign")
                    record_workflow_event(request, instance, *args, **kwargs)
                    raise RuntimeError("single operation audit failure")

                with patch("sis_common.group_audit.record_workflow_event", side_effect=failing_audit):
                    with self.assertRaisesMessage(RuntimeError, "single operation audit failure"):
                        getattr(self.client, method)(url, payload, format="json")
                group.refresh_from_db()
                assert group.name == name
                assert list(group.permissions.values_list("pk", flat=True)) == [self.grant.pk]
                assert list(group.user_set.values_list("pk", flat=True)) == before_members
                assert set(Group.objects.values_list("pk", flat=True)) == before_ids
                assert WorkflowEvent.objects.count() == event_count

    def test_out_of_scope_and_scoped_permissions_cannot_be_delegated(self):
        event_count = WorkflowEvent.objects.count()
        response = self.client.post(
            f"{BASE}groupes/", {"name": "forbidden-grant", "permissions": [self.forbidden.pk]}, format="json"
        )
        assert response.status_code == 400, response.data
        assert not Group.objects.filter(name="forbidden-grant").exists()
        group = Group.objects.create(name="existing-group")
        response = self.client.patch(f"{BASE}groupes/{group.pk}/", {"permissions": [self.forbidden.pk]}, format="json")
        assert response.status_code == 400, response.data
        assert not group.permissions.exists()
        group.permissions.add(self.forbidden)
        assert self.client.post(f"{BASE}groupes/{group.pk}/assign/", {"user_id": self.student.pk}).status_code == 403
        assert not self.student.groups.filter(pk=group.pk).exists()
        self.admin.attributs_acces = {"permission_scopes": {"utilisateurs.view_utilisateur": {"classes": [1]}}}
        self.admin.save(update_fields=["attributs_acces"])
        response = self.client.post(
            f"{BASE}groupes/", {"name": "scoped-grant", "permissions": [self.grant.pk]}, format="json"
        )
        assert response.status_code == 400, response.data
        assert WorkflowEvent.objects.count() == event_count

    def test_self_promotion_and_direct_account_bypasses_are_denied(self):
        event_count = WorkflowEvent.objects.count()
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
        response = self.client.patch(f"{BASE}comptes/{self.student.pk}/", {"role": "doyen"}, format="json")
        assert response.status_code == 400, response.data
        response = self.client.patch(f"{BASE}comptes/{self.student.pk}/", {"groups": [group.pk]}, format="json")
        assert response.status_code == 400, response.data
        self.student.refresh_from_db()
        assert self.student.role == "etudiant"
        assert not self.student.groups.exists()
        assert WorkflowEvent.objects.count() == event_count

    def test_foreign_institution_account_and_assignment_are_denied(self):
        event_count = WorkflowEvent.objects.count()
        foreign = type(self.tenant)(schema_name="group_author_foreign")
        self.setup_tenant(foreign)
        foreign.auto_create_schema = False
        with schema_context("public"):
            foreign.save()
        outsider = Utilisateur.objects.create_user(
            "foreign-author", role="doyen", etablissement=foreign, is_superuser=True
        )
        target = Utilisateur.objects.create_user("foreign-target", role="etudiant", etablissement=foreign)
        group = Group.objects.create(name="local-only")
        for action in ("assign", "unassign"):
            with self.subTest(action=action):
                response = self.client.post(f"{BASE}groupes/{group.pk}/{action}/", {"user_id": target.pk})
                assert response.status_code == 404, response.data
        self.client.force_authenticate(outsider)
        assert self.client.post(f"{BASE}groupes/", {"name": "foreign-write"}).status_code == 403
        assert self.client.get(f"{BASE}groupes/").status_code == 403
        assert not Group.objects.filter(name="foreign-write").exists()
        assert not group.user_set.exists()
        assert WorkflowEvent.objects.count() == event_count

    def test_unprivileged_user_cannot_create_or_assign_groups(self):
        group = Group.objects.create(name="admin-only")
        group.permissions.add(self.grant)
        self.student.groups.add(group)
        event_count = WorkflowEvent.objects.count()
        self.client.force_authenticate(self.student)
        for method, suffix, payload in (
            ("post", "", {"name": "not-allowed"}),
            ("patch", f"{group.pk}/", {"name": "not-allowed", "permissions": []}),
            ("delete", f"{group.pk}/", {}),
            ("post", f"{group.pk}/assign/", {"user_id": self.admin.pk}),
            ("post", f"{group.pk}/unassign/", {"user_id": self.student.pk}),
        ):
            with self.subTest(method=method, suffix=suffix):
                response = getattr(self.client, method)(f"{BASE}groupes/{suffix}", payload, format="json")
                assert response.status_code == 403, response.data
                group.refresh_from_db()
                assert group.name == "admin-only"
                assert list(group.permissions.values_list("pk", flat=True)) == [self.grant.pk]
                assert list(group.user_set.values_list("pk", flat=True)) == [self.student.pk]
                assert not Group.objects.filter(name="not-allowed").exists()
                assert WorkflowEvent.objects.count() == event_count

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
        root = Utilisateur.objects.create_superuser("root-group-author", role="super_admin")
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
    domain = "group-author-superieur.example.test"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with schema_context("public"):
            cls.peer = type(cls.tenant)(schema_name="group_author_superieur_peer")
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
