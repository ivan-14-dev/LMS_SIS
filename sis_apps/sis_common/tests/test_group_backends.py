"""Real tenant-database regressions, executed separately under each SIS settings."""

from unittest.mock import patch

from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.utilisateurs.models import GroupLifecycle, Utilisateur
from asgiref.sync import async_to_sync
from django.contrib.auth.models import AnonymousUser, Group, Permission
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from guardian.core import ObjectPermissionChecker
from guardian.exceptions import WrongAppError
from guardian.models import GroupObjectPermission, UserObjectPermission
from guardian.shortcuts import assign_perm
from guardian.utils import get_anonymous_user

from sis_common.authorization import permission_snapshot
from sis_common.group_backends import ActiveGroupModelBackend, ActiveGroupObjectPermissionBackend

MODEL_BACKEND = "sis_common.group_backends.ActiveGroupModelBackend"


class ActiveGroupBackendTests(TenantAPITestCase):
    def setUp(self):
        self.user = Utilisateur.objects.create_user("lifecycle-member", etablissement=self.tenant)
        self.group = Group.objects.create(name="lifecycle-source")
        self.other = Group.objects.create(name="lifecycle-other")
        self.resource = Group.objects.create(name="object-permission-resource")
        self.user.groups.add(self.group, self.other)
        self.view = Permission.objects.get(content_type__app_label="auth", codename="view_group")
        self.change = Permission.objects.get(content_type__app_label="auth", codename="change_group")
        self.delete = Permission.objects.get(content_type__app_label="auth", codename="delete_group")

    def fresh_user(self):
        return Utilisateur.objects.get(pk=self.user.pk)

    def test_model_permissions_and_async_interfaces_filter_only_inactive_groups(self):
        self.group.permissions.add(self.view, self.change)
        self.other.permissions.add(self.change)
        self.user.user_permissions.add(self.delete)
        for state in (None, False, True):
            if state is not None:
                GroupLifecycle.objects.update_or_create(group=self.group, defaults={"actif": state})
            expected = {"auth.change_group", "auth.delete_group"}
            group_expected = {"auth.change_group"}
            if state is not False:
                expected.add("auth.view_group")
                group_expected.add("auth.view_group")
            user = self.fresh_user()
            assert user.get_all_permissions() == expected
            assert user.get_group_permissions() == group_expected
            assert user.get_user_permissions() == {"auth.delete_group"}
            assert user.has_perm("auth.view_group") is (state is not False)
            assert user.has_module_perms("auth")
            assert async_to_sync(self.fresh_user().aget_all_permissions)() == expected
            assert async_to_sync(self.fresh_user().aget_group_permissions)() == group_expected
            assert async_to_sync(self.fresh_user().ahas_perm)("auth.view_group") is (state is not False)
        self.other.permissions.clear()
        self.user.user_permissions.clear()
        GroupLifecycle.objects.filter(group=self.group).update(actif=False)
        assert not self.fresh_user().has_module_perms("auth")
        assert not async_to_sync(self.fresh_user().ahas_module_perms)("auth")
        assert set(self.group.permissions.values_list("pk", flat=True)) == {self.view.pk, self.change.pk}
        assert set(self.user.groups.values_list("pk", flat=True)) == {self.group.pk, self.other.pk}

    def test_with_perm_uses_same_grants_without_cross_user_or_group_join_leaks(self):
        self.group.permissions.add(self.view)
        # Another active group has the same permission but not this user.
        stranger = Utilisateur.objects.create_user("lifecycle-stranger", etablissement=self.tenant)
        unrelated = Group.objects.create(name="unrelated-active")
        unrelated.permissions.add(self.view)
        stranger.groups.add(unrelated)
        direct = Utilisateur.objects.create_user("lifecycle-direct", etablissement=self.tenant)
        direct.user_permissions.add(self.view)
        inactive = Utilisateur.objects.create_user("lifecycle-inactive", is_active=False, etablissement=self.tenant)
        inactive.user_permissions.add(self.view)
        root = Utilisateur.objects.create_superuser("lifecycle-root", etablissement=self.tenant)
        GroupLifecycle.objects.create(group=self.group, actif=False)
        for perm in ("auth.view_group", self.view):
            assert set(Utilisateur.objects.with_perm(perm, backend=MODEL_BACKEND)) == {stranger, direct, root}
            assert set(Utilisateur.objects.with_perm(perm, backend=MODEL_BACKEND, include_superusers=False)) == {
                stranger,
                direct,
            }
            assert set(Utilisateur.objects.with_perm(perm, backend=MODEL_BACKEND, is_active=False)) == {inactive}
            assert set(Utilisateur.objects.with_perm(perm, backend=MODEL_BACKEND, is_active=None)) == {
                stranger,
                direct,
                inactive,
                root,
            }
            assert not Utilisateur.objects.with_perm(perm, backend=MODEL_BACKEND, obj=self.resource).exists()
        GroupLifecycle.objects.filter(group=self.group).update(actif=True)
        assert self.user in Utilisateur.objects.with_perm(self.view, backend=MODEL_BACKEND)
        with self.assertRaises(ValueError):
            Utilisateur.objects.with_perm("invalid", backend=MODEL_BACKEND)
        with self.assertRaises(TypeError):
            Utilisateur.objects.with_perm(1, backend=MODEL_BACKEND)

    def test_snapshot_filters_disabled_names_and_keeps_independent_configured_grants(self):
        self.group.permissions.add(self.view)
        self.other.permissions.add(self.change)
        configuration = {
            "permission_groups": [
                {"code": "configured-view", "permissions": ["auth.view_group"]},
                {"code": "configured-change", "permissions": ["auth.change_group"]},
            ]
        }
        for state in (None, False, True):
            if state is not None:
                GroupLifecycle.objects.update_or_create(group=self.group, defaults={"actif": state})
            expected = {self.other.name, "configured-change"}
            if state is not False:
                expected.update({self.group.name, "configured-view"})
            assert set(permission_snapshot(self.fresh_user(), configuration)["groups"]) == expected

        GroupLifecycle.objects.filter(group=self.group).update(actif=False)
        self.user.user_permissions.add(self.view)
        assert set(permission_snapshot(self.fresh_user(), configuration)["groups"]) == {
            self.other.name,
            "configured-view",
            "configured-change",
        }
        assert set(self.user.groups.values_list("pk", flat=True)) == {self.group.pk, self.other.pk}

    def test_guardian_object_grants_are_filtered_without_changing_assignments(self):
        assign_perm(self.view, self.group, self.resource)
        assign_perm(self.change, self.group, self.resource)
        assign_perm(self.change, self.other, self.resource)
        assign_perm(self.delete, self.user, self.resource)
        group_rows = list(GroupObjectPermission.objects.order_by("pk").values())
        direct_rows = list(UserObjectPermission.objects.order_by("pk").values())
        for state in (None, False, True):
            if state is not None:
                GroupLifecycle.objects.update_or_create(group=self.group, defaults={"actif": state})
            user = self.fresh_user()
            expected = {"change_group", "delete_group"}
            if state is not False:
                expected.add("view_group")
            assert user.get_all_permissions(self.resource) == expected
            assert user.get_group_permissions(self.resource) == expected - {"delete_group"}
            assert user.get_user_permissions(self.resource) == {"delete_group"}
            assert user.has_perm("auth.view_group", self.resource) is (state is not False)
            assert user.has_perm("view_group", self.resource) is (state is not False)
            assert user.has_perm("auth.change_group", self.resource)
            assert user.has_perm("auth.delete_group", self.resource)
            assert user.get_all_permissions() == set()
            assert not user.has_module_perms("auth")
            assert async_to_sync(self.fresh_user().ahas_perm)("auth.view_group", self.resource) is (state is not False)
            assert async_to_sync(self.fresh_user().aget_all_permissions)(self.resource) == expected
        assert list(GroupObjectPermission.objects.order_by("pk").values()) == group_rows
        assert list(UserObjectPermission.objects.order_by("pk").values()) == direct_rows
        assert set(self.user.groups.values_list("pk", flat=True)) == {self.group.pk, self.other.pk}

    def test_guardian_prefetch_cache_does_not_restore_disabled_grants(self):
        assign_perm(self.view, self.group, self.resource)
        with patch("guardian.conf.settings.AUTO_PREFETCH", True):
            assert ObjectPermissionChecker(self.user).has_perm("auth.view_group", self.resource)
            assert hasattr(self.user, "_guardian_perms_cache")
            GroupLifecycle.objects.create(group=self.group, actif=False)
            backend = ActiveGroupObjectPermissionBackend()
            assert not backend.has_perm(self.user, "auth.view_group", self.resource)
            assert backend.get_all_permissions(self.user, self.resource) == set()
            assert backend.get_group_permissions(self.user, self.resource) == set()

    def test_object_backend_keeps_guardian_principal_and_app_label_semantics(self):
        backend = ActiveGroupObjectPermissionBackend()
        root = Utilisateur.objects.create_superuser("object-lifecycle-root", etablissement=self.tenant)
        assert backend.has_perm(root, "auth.view_group", self.resource)
        root.is_active = False
        assert not backend.has_perm(root, "auth.view_group", self.resource)
        assert backend.get_all_permissions(root, self.resource) == set()
        self.user.is_active = False
        assign_perm(self.view, self.user, self.resource)
        assert not backend.has_perm(self.user, "auth.view_group", self.resource)
        assert backend.get_user_permissions(self.user, self.resource) == set()
        assert not backend.has_perm(self.user, "auth.view_group")
        assert not backend.has_perm(self.user, "auth.view_group", object())
        with self.assertRaises(WrongAppError):
            backend.has_perm(self.user, "utilisateurs.view_group", self.resource)
        anonymous = get_anonymous_user()
        anonymous.groups.add(self.group)
        assign_perm(self.view, self.group, self.resource)
        assert backend.has_perm(AnonymousUser(), "auth.view_group", self.resource)
        GroupLifecycle.objects.create(group=self.group, actif=False)
        assert not backend.has_perm(AnonymousUser(), "auth.view_group", self.resource)

    def test_disabling_group_does_not_disable_local_authentication(self):
        self.user.set_password("lifecycle-local-test-password")
        self.user.save(update_fields=["password"])
        GroupLifecycle.objects.create(group=self.group, actif=False)
        backend = ActiveGroupModelBackend()
        assert (
            backend.authenticate(None, username=self.user.username, password="lifecycle-local-test-password")
            == self.user
        )
        assert backend.get_user(self.user.pk) == self.user
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        assert backend.authenticate(None, username=self.user.username, password="lifecycle-local-test-password") is None
        assert backend.get_user(self.user.pk) is None


class GroupLifecycleMigrationTests(TenantAPITestCase):
    def test_migration_preserves_legacy_rows_and_requires_no_lifecycle_backfill(self):
        before = [("utilisateurs", "0005_utilisateur_integration_id")]
        after = [("utilisateurs", "0006_group_lifecycle")]
        MigrationExecutor(connection).migrate(before)
        try:
            group = Group.objects.create(name="pre-lifecycle-migration")
            user = Utilisateur.objects.create_user("pre-lifecycle-member", etablissement=self.tenant)
            permission = Permission.objects.get(content_type__app_label="auth", codename="view_group")
            user.groups.add(group)
            group.permissions.add(permission)
            assign_perm(permission, group, group)
            before_group_rows = list(Group.objects.order_by("pk").values())
            before_members = list(Utilisateur.groups.through.objects.order_by("pk").values())
            before_grants = list(Group.permissions.through.objects.order_by("pk").values())
            before_objects = list(GroupObjectPermission.objects.order_by("pk").values())
            MigrationExecutor(connection).migrate(after)
            assert not GroupLifecycle.objects.exists()
            assert list(Group.objects.order_by("pk").values()) == before_group_rows
            assert list(Utilisateur.groups.through.objects.order_by("pk").values()) == before_members
            assert list(Group.permissions.through.objects.order_by("pk").values()) == before_grants
            assert list(GroupObjectPermission.objects.order_by("pk").values()) == before_objects
            current = Utilisateur.objects.get(pk=user.pk)
            assert current.has_perm("auth.view_group")
            assert current.has_perm("auth.view_group", group)
        finally:
            MigrationExecutor(connection).migrate(after)
