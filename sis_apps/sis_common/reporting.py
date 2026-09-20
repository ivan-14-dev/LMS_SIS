"""Safe, allow-listed CSV exports for tenant-configured reports."""

import csv
from io import StringIO

from django.http import HttpResponse
from rest_framework.exceptions import ValidationError


def _has_any_permission(user, permissions):
    if not permissions:
        return True
    if getattr(user, "is_superuser", False):
        return True
    return any(user.has_perm(permission) for permission in permissions)


def configured_report(request, code, allowed_datasets=None):
    reports = getattr(request.tenant, "configuration_academique", {}).get("reports", [])
    report = next((item for item in reports if item.get("code") == code), None)
    if not report:
        raise ValidationError({"report": "Rapport inconnu ou non activé."})
    dataset = report.get("dataset")
    if allowed_datasets and dataset not in allowed_datasets:
        raise ValidationError({"report": "Ce rapport n'est pas disponible depuis ce module."})
    required_permissions = report.get("required_permissions", [])
    if required_permissions and not _has_any_permission(request.user, required_permissions):
        raise ValidationError({"report": "Vous n'avez pas accès à ce rapport."})
    return report


def export_queryset_csv(queryset, report, field_map, filter_map, supplied_filters):
    fields = report.get("fields", [])
    unknown_fields = set(fields) - set(field_map)
    if unknown_fields:
        raise ValidationError({"fields": f"Champs non exportables: {', '.join(sorted(unknown_fields))}."})
    allowed_filters = set(report.get("allowed_filters", []))
    unknown_filters = set(supplied_filters) - allowed_filters
    if unknown_filters:
        raise ValidationError({"filters": f"Filtres non autorisés: {', '.join(sorted(unknown_filters))}."})
    orm_filters = {}
    for name, value in supplied_filters.items():
        if name not in filter_map:
            raise ValidationError({"filters": f"Filtre inconnu: {name}."})
        orm_filters[filter_map[name]] = value
    queryset = queryset.filter(**orm_filters)

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow([field_map[field][0] for field in fields])
    orm_fields = [field_map[field][1] for field in fields]
    writer.writerows(queryset.values_list(*orm_fields).distinct())
    response = HttpResponse(output.getvalue(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{report["code"]}.csv"'
    return response
