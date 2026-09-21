"""Shared helpers for submission windows and reminders."""

from datetime import datetime, time, timedelta

from django.apps import apps
from django.utils import timezone

from sis_common.authorization import configured_permission_groups
from sis_common.academic_configuration import resolve_submission_window_settings
from sis_common.workflow_tracking import record_workflow_event

WINDOW_KIND_LABELS = {
    "evaluation": "soumission",
    "exam": "soumission des résultats",
}


def _reference_start(instance):
    current_date = getattr(instance, "date", None)
    current_time = getattr(instance, "heure_debut", None) or time.min
    if current_date is None:
        return timezone.now()
    value = datetime.combine(current_date, current_time)
    if timezone.is_naive(value):
        value = timezone.make_aware(value, timezone.get_current_timezone())
    return value


def _reference_end(instance):
    return _reference_start(instance) + timedelta(
        minutes=int(getattr(instance, "duree_minutes", 0) or 0)
    )


def apply_submission_window_defaults(instance, configuration, window_type):
    settings = resolve_submission_window_settings(configuration, window_type)
    if not settings.get("enabled", True):
        return []
    changed_fields = []
    if getattr(instance, "debut_soumission", None) is None:
        instance.debut_soumission = _reference_start(instance) + timedelta(
            hours=int(settings.get("default_open_offset_hours", 0) or 0)
        )
        changed_fields.append("debut_soumission")
    if getattr(instance, "fin_soumission", None) is None:
        instance.fin_soumission = _reference_end(instance) + timedelta(
            hours=int(settings.get("default_close_offset_hours", 0) or 0)
        )
        changed_fields.append("fin_soumission")
    return changed_fields


def get_submission_window_status(instance, now=None):
    now = now or timezone.now()
    start = getattr(instance, "debut_soumission", None)
    end = getattr(instance, "fin_soumission", None)
    if start and now < start:
        return "a_venir"
    if end and now > end:
        return "fermee"
    if start or end:
        return "ouverte"
    return "non_planifiee"


def get_submission_window_alert(instance, configuration, window_type, now=None):
    settings = resolve_submission_window_settings(configuration, window_type)
    if not settings.get("enabled", True):
        return None
    now = now or timezone.now()
    deadline = getattr(instance, "fin_soumission", None)
    if not deadline or now > deadline:
        return None
    remaining = deadline - now
    reminder_hours = sorted(
        {int(hours) for hours in settings.get("reminder_hours", []) if isinstance(hours, int)},
    )
    for hours in reminder_hours:
        if remaining <= timedelta(hours=hours):
            return {
                "severity": "warning",
                "threshold_hours": hours,
                "message": f"Clôture de la {WINDOW_KIND_LABELS[window_type]} dans moins de {hours}h.",
            }
    return None


def _normalize_recipient(recipient):
    if recipient is None:
        return None
    user = getattr(recipient, "user", None)
    if user is not None:
        recipient = user
    if getattr(recipient, "pk", None) is None:
        return None
    return recipient


def _deduplicate_recipients(recipients):
    unique = []
    seen = set()
    for recipient in recipients:
        normalized = _normalize_recipient(recipient)
        if normalized is None or normalized.pk in seen:
            continue
        seen.add(normalized.pk)
        unique.append(normalized)
    return unique


def _role_recipients(role_codes):
    if not role_codes:
        return []
    user_model = apps.get_model("utilisateurs", "Utilisateur")
    return list(user_model.objects.filter(is_active=True, role__in=role_codes))


def _group_recipients(configuration, group_codes):
    if not group_codes:
        return []
    user_model = apps.get_model("utilisateurs", "Utilisateur")
    recipients = []
    for user in user_model.objects.filter(is_active=True):
        if any(code in configured_permission_groups(user, configuration) for code in group_codes):
            recipients.append(user)
    return recipients


def resolve_submission_window_recipients(instance, configuration, window_type, assigned_recipients=None):
    settings = resolve_submission_window_settings(configuration, window_type)
    recipients = []
    if settings.get("notify_assigned_users", True):
        recipients.extend(assigned_recipients or [])
    recipients.extend(_role_recipients(settings.get("recipient_role_codes", [])))
    recipients.extend(_group_recipients(configuration, settings.get("recipient_group_codes", [])))
    return _deduplicate_recipients(recipients)


def maybe_record_submission_window_alert(request, instance, configuration, window_type, recipients):
    alert = get_submission_window_alert(instance, configuration, window_type)
    if not alert:
        return
    recipients = resolve_submission_window_recipients(
        instance,
        configuration,
        window_type,
        assigned_recipients=recipients,
    )
    WorkflowEvent = apps.get_model("core", "WorkflowEvent")
    action = f"{window_type}_submission_deadline_{alert['threshold_hours']}h"
    meta = instance._meta
    already_exists = WorkflowEvent.objects.filter(
        tenant_id=getattr(getattr(request, "tenant", None), "id", None),
        app_label=meta.app_label,
        model=meta.model_name,
        object_id=str(instance.pk),
        action=action,
    ).exists()
    if already_exists:
        return
    record_workflow_event(
        request,
        instance,
        action,
        "Clôture de soumission imminente",
        message=alert["message"],
        recipients=recipients,
        metadata={
            "submission_window_type": window_type,
            "threshold_hours": alert["threshold_hours"],
            "fin_soumission": getattr(instance, "fin_soumission", None).isoformat()
            if getattr(instance, "fin_soumission", None)
            else "",
        },
    )
