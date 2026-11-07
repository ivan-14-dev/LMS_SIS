"""Permission backends that retain memberships but ignore disabled groups.

Missing lifecycle rows mean active (including groups created outside the API).
Model permissions keep Django's per-user-instance cache: reload the user between
requests. Guardian checks here deliberately do not consume its prefetch cache.
Native Guardian shortcuts/checkers do not use these backends and are not covered.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import BaseBackend, ModelBackend
from django.contrib.auth.models import Group, Permission
from django.db.models import Exists, OuterRef, Q
from guardian.backends import ObjectPermissionBackend, check_support
from guardian.core import ObjectPermissionChecker
from guardian.ctypes import get_content_type
from guardian.exceptions import WrongAppError
from guardian.utils import get_group_obj_perms_model


def active_groups():
    return Group.objects.exclude(permission_lifecycle__actif=False)


def group_is_active(group):
    # Read the stored state, not a possibly cached reverse OneToOne relation.
    return not Group.objects.filter(pk=group.pk, permission_lifecycle__actif=False).exists()


def group_object_permissions(group):
    model = get_group_obj_perms_model()
    return Permission.objects.filter(pk__in=model.objects.filter(group=group).values("permission_id")).select_related(
        "content_type"
    )


class ActiveGroupModelBackend(ModelBackend):
    def _get_group_permissions(self, user_obj):
        return Permission.objects.filter(group__in=user_obj.groups.filter(pk__in=active_groups()))

    def with_perm(self, perm, is_active=True, include_superusers=True, obj=None):
        if isinstance(perm, str):
            try:
                app_label, codename = perm.split(".")
            except ValueError:
                raise ValueError("Permission name should be in the form app_label.permission_codename.")
            permissions = Permission.objects.filter(content_type__app_label=app_label, codename=codename)
        elif isinstance(perm, Permission):
            permissions = Permission.objects.filter(pk=perm.pk)
        else:
            raise TypeError("The `perm` argument must be a string or a permission instance.")

        users = get_user_model()._default_manager
        if obj is not None:
            return users.none()
        direct = permissions.filter(user=OuterRef("pk"))
        grouped = permissions.filter(group__user=OuterRef("pk"), group__in=active_groups())
        condition = Exists(direct) | Exists(grouped)
        if include_superusers:
            condition |= Q(is_superuser=True)
        if is_active is not None:
            condition &= Q(is_active=is_active)
        return users.filter(condition)


class _ActiveGroupPermissionChecker(ObjectPermissionChecker):
    def get_group_filters(self, obj):
        filters = super().get_group_filters(obj)
        model = get_group_obj_perms_model(obj)
        related_name = model.permission.field.related_query_name()
        filters[f"{related_name}__group__in"] = active_groups()
        return filters


class ActiveGroupObjectPermissionBackend(ObjectPermissionBackend, BaseBackend):
    """Guardian object semantics, with filtered groups and no shared prefetch."""

    def _permissions(self, user_obj, obj, source):
        supported, user_obj = check_support(user_obj, obj)
        if not supported or not user_obj.is_active:
            return set()
        if user_obj.is_superuser:
            return set(Permission.objects.filter(content_type=get_content_type(obj)).values_list("codename", flat=True))
        checker = _ActiveGroupPermissionChecker(user_obj)
        # get_perms()/prefetch_perms() in Guardian bypass get_group_filters when
        # AUTO_PREFETCH is enabled. Query the two filtered sources explicitly.
        if source == "user":
            return set(checker.get_user_perms(obj))
        if source == "group":
            return set(checker.get_group_perms(obj))
        return set(checker.get_user_perms(obj)) | set(checker.get_group_perms(obj))

    def get_user_permissions(self, user_obj, obj=None):
        return self._permissions(user_obj, obj, "user")

    def get_group_permissions(self, user_obj, obj=None):
        return self._permissions(user_obj, obj, "group")

    def get_all_permissions(self, user_obj, obj=None):
        return self._permissions(user_obj, obj, "all")

    def has_perm(self, user_obj, perm, obj=None):
        supported, user_obj = check_support(user_obj, obj)
        if not supported:
            return False
        if "." in perm:
            app_label, codename = perm.split(".", 1)
            if app_label != obj._meta.app_label and app_label != get_content_type(obj).app_label:
                raise WrongAppError(f"Permission app label '{app_label}' does not match the object.")
        else:
            codename = perm
        return user_obj.is_active and (user_obj.is_superuser or codename in self.get_all_permissions(user_obj, obj))

    async def ahas_perm(self, user_obj, perm, obj=None):
        # BaseBackend compares literal permission strings, unlike Guardian's
        # qualified-or-bare codename contract.
        from asgiref.sync import sync_to_async

        return await sync_to_async(self.has_perm)(user_obj, perm, obj)
