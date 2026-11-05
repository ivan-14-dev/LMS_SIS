"""Dynamic RBAC and lightweight ABAC helpers shared by both SIS variants."""


def is_current_tenant_user(request):
    """Authorization writes require an account owned by the active database tenant."""
    from django.db import connection

    tenant = getattr(request, "tenant", None)
    owner_id = getattr(request.user, "etablissement_id", None)
    return bool(
        tenant
        and getattr(connection, "schema_name", None) == tenant.schema_name
        and (owner_id == tenant.pk or (owner_id is None and request.user.is_superuser))
    )


def can_delegate_permissions(user, permissions):
    """A scoped permission cannot be delegated as an unrestricted group grant."""
    return all(
        has_business_permission(user, f"{permission.content_type.app_label}.{permission.codename}")
        for permission in permissions
    )


def validate_account_authorization_changes(request, instance, attrs, initial_data, *, default_role):
    """Keep legacy account writes from bypassing the controlled group assignment API."""
    from rest_framework.exceptions import ValidationError

    if request is None or request.user.is_superuser:
        return
    if instance is not None and instance.is_superuser:
        raise ValidationError({"detail": "Un administrateur ne peut pas modifier un super-utilisateur."})
    for field in ("groups", "user_permissions", "attributs_acces"):
        if field in initial_data:
            raise ValidationError({field: "Utilisez l'administration des groupes ou un super-utilisateur."})
    role = attrs.get("role")
    if role is not None and role != (instance.role if instance else default_role):
        raise ValidationError({"role": "Le changement de rôle hérité requiert un super-utilisateur."})


def _group_names(user):
    if not hasattr(user, "groups"):
        return []
    groups = user.groups
    if hasattr(groups, "order_by"):
        return list(groups.order_by("name").values_list("name", flat=True))
    if isinstance(groups, (list, tuple, set)):
        return list(groups)
    return []


def user_has_any_role(user, roles=()):
    return getattr(user, "role", "") in roles


def _attribute_matches(expected, actual):
    if isinstance(expected, list):
        if isinstance(actual, list):
            return any(value in expected for value in actual)
        return actual in expected
    if isinstance(actual, list):
        return expected in actual
    return actual == expected


def _matches_group_attributes(user_attributes, required_attributes):
    for attribute, expected in (required_attributes or {}).items():
        actual = user_attributes.get(attribute)
        if not _attribute_matches(expected, actual):
            return False
    return True


def configured_permission_groups(user, configuration=None):
    if not user.is_authenticated:
        return []
    if user.is_superuser:
        return [group["code"] for group in (configuration or {}).get("permission_groups", [])]

    user_attributes = getattr(user, "attributs_acces", {}) or {}
    resolved = []
    for group in (configuration or {}).get("permission_groups", []):
        permissions = group.get("permissions", [])
        if permissions and not all(user.has_perm(permission) for permission in permissions):
            continue
        if not _matches_group_attributes(user_attributes, group.get("attributes", {})):
            continue
        resolved.append(group["code"])
    return resolved


def user_in_configured_groups(user, configuration=None, group_codes=()):
    if not group_codes:
        return False
    return any(group in configured_permission_groups(user, configuration) for group in group_codes)


def permission_snapshot(user, configuration=None):
    if not user.is_authenticated:
        return {"permissions": [], "groups": [], "attributes": {}, "role": ""}
    groups = sorted(set(_group_names(user) + configured_permission_groups(user, configuration)))
    return {
        "permissions": ["*"] if user.is_superuser else sorted(user.get_all_permissions()),
        "groups": groups,
        "attributes": getattr(user, "attributs_acces", {}) or {},
        "role": getattr(user, "role", ""),
    }


def has_business_permission(user, permission, context=None):
    """Check a Django permission and optional per-user attribute constraints."""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if not user.has_perm(permission):
        return False

    configured_scopes = (getattr(user, "attributs_acces", {}) or {}).get("permission_scopes", {})
    constraints = configured_scopes.get(permission)
    if not constraints:
        return True
    if not context:
        return False
    for attribute, allowed_values in constraints.items():
        if attribute not in context:
            return False
        if not isinstance(allowed_values, list) or context[attribute] not in allowed_values:
            return False
    return True


def has_business_permission_or_role(
    user,
    permission,
    legacy_roles=(),
    context=None,
    configuration=None,
    tenant_group_codes=(),
):
    """Honor dynamic Django permissions while retaining legacy role compatibility."""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if user.has_perm(permission):
        return has_business_permission(user, permission, context=context)
    if user_in_configured_groups(user, configuration, tenant_group_codes):
        return True
    return getattr(user, "role", "") in legacy_roles


def request_has_business_access(
    request,
    permission,
    legacy_roles=(),
    *,
    context=None,
    tenant_group_codes=(),
):
    return has_business_permission_or_role(
        request.user,
        permission,
        legacy_roles,
        context=context,
        configuration=getattr(getattr(request, "tenant", None), "configuration_academique", {}),
        tenant_group_codes=tenant_group_codes,
    )


def request_has_role_or_business_access(
    request,
    permission,
    legacy_roles=(),
    *,
    context=None,
    tenant_group_codes=(),
):
    return request_has_business_access(
        request,
        permission,
        legacy_roles,
        context=context,
        tenant_group_codes=tenant_group_codes,
    ) or user_has_any_role(request.user, legacy_roles)


def filter_queryset_by_scopes(queryset, user, permission, scope_fields):
    """Apply configured ABAC lists to a queryset; unknown scopes deny access."""
    if user.is_superuser:
        return queryset
    constraints = (getattr(user, "attributs_acces", {}) or {}).get("permission_scopes", {}).get(permission, {})
    for attribute, allowed_values in constraints.items():
        lookup = scope_fields.get(attribute)
        if not lookup or not isinstance(allowed_values, list):
            return queryset.none()
        queryset = queryset.filter(**{f"{lookup}__in": allowed_values})
    return queryset.distinct()
