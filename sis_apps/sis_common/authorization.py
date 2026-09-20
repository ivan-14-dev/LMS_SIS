"""Dynamic RBAC and lightweight ABAC helpers shared by both SIS variants."""


def permission_snapshot(user):
    if not user.is_authenticated:
        return {"permissions": [], "groups": [], "attributes": {}, "role": ""}
    return {
        "permissions": ["*"] if user.is_superuser else sorted(user.get_all_permissions()),
        "groups": list(user.groups.order_by("name").values_list("name", flat=True)),
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

    configured_scopes = (getattr(user, "attributs_acces", {}) or {}).get(
        "permission_scopes", {}
    )
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
    user, permission, legacy_roles=(), context=None
):
    """Honor dynamic Django permissions while retaining legacy role compatibility."""
    if not user.is_authenticated:
        return False
    if user.is_superuser or user.is_staff:
        return True
    if user.has_perm(permission):
        return has_business_permission(user, permission, context=context)
    return getattr(user, "role", "") in legacy_roles


def filter_queryset_by_scopes(queryset, user, permission, scope_fields):
    """Apply configured ABAC lists to a queryset; unknown scopes deny access."""
    if user.is_superuser:
        return queryset
    constraints = (getattr(user, "attributs_acces", {}) or {}).get(
        "permission_scopes", {}
    ).get(permission, {})
    for attribute, allowed_values in constraints.items():
        lookup = scope_fields.get(attribute)
        if not lookup or not isinstance(allowed_values, list):
            return queryset.none()
        queryset = queryset.filter(**{f"{lookup}__in": allowed_values})
    return queryset.distinct()
