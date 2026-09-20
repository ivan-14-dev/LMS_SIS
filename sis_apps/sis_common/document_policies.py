"""Reusable document workflow helpers for tenant-driven publication/signature rules."""

from functools import wraps

from django.apps import apps
from rest_framework.response import Response

from sis_common.academic_configuration import resolve_validation_policy

OPEN_FINANCIAL_STATUSES = ("emise", "partielle", "en_retard")


def get_action_object(view):
    return getattr(view, "_financial_clearance_object", None) or view.get_object()


def requires_financial_clearance(configuration, candidates):
    policy = resolve_validation_policy(configuration, candidates)
    return bool((policy or {}).get("publication", {}).get("requires_financial_clearance"))


def subject_has_financial_clearance(
    subject,
    academic_year_ids,
    *,
    invoice_model_label,
    invoice_subject_field,
    invoice_year_lookup,
    open_statuses=OPEN_FINANCIAL_STATUSES,
):
    invoice_model = apps.get_model(invoice_model_label)
    if not academic_year_ids:
        return True
    return not invoice_model.objects.filter(
        **{
            invoice_subject_field: subject,
            f"{invoice_year_lookup}__in": academic_year_ids,
            "statut__in": open_statuses,
        }
    ).exists()


def enforce_financial_clearance(
    *,
    candidates_getter,
    subject_getter,
    academic_year_ids_getter,
    invoice_model_label,
    invoice_subject_field,
    invoice_year_lookup,
    message,
):
    """Decorator that blocks an action when tenant policy requires financial clearance."""

    def decorator(func):
        @wraps(func)
        def wrapped(view, request, *args, **kwargs):
            obj = view.get_object()
            view._financial_clearance_object = obj
            try:
                configuration = getattr(request.tenant, "configuration_academique", {})
                candidates = candidates_getter(view, request, obj)
                if requires_financial_clearance(configuration, candidates):
                    subject = subject_getter(view, request, obj)
                    academic_year_ids = academic_year_ids_getter(view, request, obj)
                    if not subject_has_financial_clearance(
                        subject,
                        academic_year_ids,
                        invoice_model_label=invoice_model_label,
                        invoice_subject_field=invoice_subject_field,
                        invoice_year_lookup=invoice_year_lookup,
                    ):
                        return Response({"error": message}, status=409)
                return func(view, request, *args, **kwargs)
            finally:
                if hasattr(view, "_financial_clearance_object"):
                    delattr(view, "_financial_clearance_object")

        return wrapped

    return decorator
