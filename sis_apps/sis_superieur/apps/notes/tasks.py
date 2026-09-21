"""Celery tasks for notes."""

from datetime import timedelta
from types import SimpleNamespace

from celery import shared_task
from django.utils import timezone
from django_tenants.utils import get_tenant_model, schema_context

from sis_common.academic_configuration import resolve_submission_window_settings
from sis_common.submission_windows import maybe_record_submission_window_alert


def _scheduler_request(tenant):
    return SimpleNamespace(
        tenant=tenant,
        user=None,
        request_id="scheduler-superieur-notes-submission-windows",
    )


@shared_task
def emit_submission_window_reminders():
    tenant_model = get_tenant_model()
    now = timezone.now()
    for tenant in tenant_model.objects.filter(actif=True):
        configuration = getattr(tenant, "configuration_academique", {}) or {}
        settings = resolve_submission_window_settings(configuration, "evaluation")
        reminder_hours = [hours for hours in settings.get("reminder_hours", []) if isinstance(hours, int) and hours > 0]
        if not settings.get("enabled", True) or not reminder_hours:
            continue
        with schema_context(tenant.schema_name):
            from apps.notes.models import Evaluation

            deadline = now + timedelta(hours=max(reminder_hours))
            evaluations = Evaluation.objects.select_related("enseignant").filter(
                fin_soumission__isnull=False,
                fin_soumission__gte=now,
                fin_soumission__lte=deadline,
            )
            request = _scheduler_request(tenant)
            for evaluation in evaluations:
                recipient = getattr(evaluation, "enseignant", None)
                maybe_record_submission_window_alert(
                    request,
                    evaluation,
                    configuration,
                    "evaluation",
                    [recipient] if recipient is not None else [],
                )
