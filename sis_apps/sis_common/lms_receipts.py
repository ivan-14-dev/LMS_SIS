"""Remote receipts may confirm bindings, never create or reactivate identities."""


def confirm_account(model, payload):
    from django.db import transaction
    from django.utils import timezone

    data = payload.get("data", payload)
    user = data.get("user") or {}
    username = user.get("username") or (user.get("pii") or {}).get("username")
    remote_id = user.get("id")
    if not username or type(remote_id) is not int or remote_id <= 0:
        return False
    with transaction.atomic():
        mapping = model.objects.select_for_update().filter(username_edx=username).first()
        if (
            mapping is None
            or not mapping.actif
            or not mapping.user_sis.is_active
            or mapping.user_id_edx not in (None, remote_id)
        ):
            return False
        mapping.user_id_edx = remote_id
        mapping.date_sync = timezone.now()
        mapping.save(update_fields=["user_id_edx", "date_sync"])
    return True


def enrollment_receipt_allowed(mapping, course, active):
    from apps.integration.models import EdxAccessIntent

    from sis_common.lms_access_sync import revocation_reason

    if type(active) is not bool:
        return False
    if active and revocation_reason(mapping.user_sis, course, mapping, "enrollment"):
        return False
    intent = EdxAccessIntent.objects.filter(
        user=mapping.user_sis, course=course, kind="enrollment",
    ).first()
    return intent is None or intent.is_active is active


def update_enrollment_receipts(queryset, learner_field, active):
    from apps.integration.models import EdxUserMapping
    from django.db import transaction
    from django.utils import timezone

    with transaction.atomic():
        rows = list(queryset.select_for_update())
        if not rows:
            return False
        for row in rows:
            mapping = EdxUserMapping.objects.get(user_sis=getattr(row, learner_field).user)
            if not enrollment_receipt_allowed(mapping, row.course, active):
                return False
        queryset.update(
            is_active=active, last_sync=timezone.now(),
            date_desinscription=None if active else timezone.now(),
        )
    return True
