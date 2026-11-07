"""Atomic, audited group membership batches shared by both SIS variants."""

from django.db import transaction

from sis_common.authorization import has_business_permission
from sis_common.workflow_tracking import record_workflow_event


def can_change_group_assignments(user):
    permissions = ("auth.change_group", "utilisateurs.change_utilisateur", "utilisateurs.view_utilisateur")
    scopes = (user.attributs_acces or {}).get("permission_scopes", {})
    return user.is_active and all(
        has_business_permission(user, permission) and (user.is_superuser or permission not in scopes)
        for permission in permissions
    )


@transaction.atomic
def change_group_assignments(view, request, serializer_class, *, remove=False):
    group = view.get_object()
    serializer = serializer_class(data=request.data)
    serializer.is_valid(raise_exception=True)
    user_ids = sorted(serializer.validated_data["user_ids"])
    # Keep the existing tenant/self/superuser guards and lock all targets in PK order
    # before changing any membership.
    users = [view._assignment_target(request, user_id) for user_id in user_ids]
    existing = set(group.user_set.filter(pk__in=user_ids).values_list("pk", flat=True))
    if remove:
        group.user_set.remove(*users)
        changes = {"removed_user_ids": sorted(existing)}
    else:
        group.user_set.add(*users)
        changes = {"added_user_ids": sorted(set(user_ids) - existing)}
    result = {"group_id": group.pk, "user_ids": user_ids}
    record_workflow_event(
        request,
        group,
        "unassign_many" if remove else "assign_many",
        "Retrait de groupe en lot" if remove else "Affectation de groupe en lot",
        metadata={**result, **changes},
    )
    return result
