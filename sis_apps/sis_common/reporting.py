"""Safe, allow-listed CSV exports for tenant-configured reports."""

import csv
from io import StringIO

from django.http import HttpResponse
from rest_framework.exceptions import ValidationError


def configured_report(request, code):
    reports = getattr(request.tenant, "configuration_academique", {}).get("reports", [])
    report = next((item for item in reports if item.get("code") == code), None)
    if not report:
        raise ValidationError({"report": "Rapport inconnu ou non activé."})
    return report


def export_queryset_csv(queryset, report, field_map, filter_map, supplied_filters):
    fields = report.get("fields", [])
    unknown_fields = set(fields) - set(field_map)
    if unknown_fields:
        raise ValidationError(
            {"fields": f"Champs non exportables: {', '.join(sorted(unknown_fields))}."}
        )
    allowed_filters = set(report.get("allowed_filters", []))
    unknown_filters = set(supplied_filters) - allowed_filters
    if unknown_filters:
        raise ValidationError(
            {"filters": f"Filtres non autorisés: {', '.join(sorted(unknown_filters))}."}
        )
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
