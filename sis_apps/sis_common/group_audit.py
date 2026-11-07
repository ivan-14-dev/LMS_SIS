"""Atomic audit of group authoring and single-account assignments."""

from copy import copy

from django.db import transaction

from sis_common.workflow_tracking import record_workflow_event


def _group_snapshot(group):
    return {
        "name": group.name,
        "permissions": [
            {"id": permission.pk, "code": f"{permission.content_type.app_label}.{permission.codename}"}
            for permission in group.permissions.select_related("content_type").order_by("pk")
        ],
    }


class GroupAuditMixin:
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    def perform_create(self, serializer):
        super().perform_create(serializer)
        group = serializer.instance
        record_workflow_event(
            self.request,
            group,
            "group_created",
            "Création de groupe",
            metadata={"group_id": group.pk, "before": None, "after": _group_snapshot(group)},
        )

    def perform_update(self, serializer):
        before = _group_snapshot(serializer.instance)
        super().perform_update(serializer)
        group = serializer.instance
        record_workflow_event(
            self.request,
            group,
            "group_updated",
            "Modification de groupe",
            metadata={"group_id": group.pk, "before": before, "after": _group_snapshot(group)},
        )

    def perform_destroy(self, instance):
        before = _group_snapshot(instance)
        # Django clears the deleted instance's PK; retain its audit identity.
        identity = copy(instance)
        super().perform_destroy(instance)
        record_workflow_event(
            self.request,
            identity,
            "group_deleted",
            "Suppression de groupe",
            metadata={"group_id": identity.pk, "before": before, "after": None},
        )


@transaction.atomic
def change_group_assignment(view, request, serializer_class, *, remove=False):
    group = view.get_object()
    serializer = serializer_class(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = view._assignment_target(request, serializer.validated_data["user_id"])
    before = _group_snapshot(group)
    existing = user.groups.filter(pk=group.pk).exists()
    changed = existing if remove else not existing
    if changed:
        if remove:
            user.groups.remove(group)
        else:
            user.groups.add(group)
    result = {"user_id": user.pk, "group_id": group.pk}
    record_workflow_event(
        request,
        group,
        "unassign" if remove else "assign",
        "Retrait de groupe" if remove else "Affectation de groupe",
        metadata={
            **result,
            "before": before,
            "after": _group_snapshot(group),
            "removed_user_ids" if remove else "added_user_ids": [user.pk] if changed else [],
        },
    )
    return result
