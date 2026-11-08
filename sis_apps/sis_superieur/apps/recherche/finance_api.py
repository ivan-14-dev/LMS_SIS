"""Project-scoped read endpoints and the sole research financial command."""

import csv
from pathlib import Path

from django.http import FileResponse, HttpResponse
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from sis_common.exam_files import hash_uploaded_file
from sis_common.reporting import _csv_cell

from .access import ResearchAccess, ResearchConflict
from .finance import (
    locked_financial_project,
    money,
    post_financial_operation,
    reconciled_ledger,
    report_from_ledger,
    valid_proof_path,
)
from .finance_serializers import FinancialOperationSerializer


def _private(response):
    response["Cache-Control"] = "private, no-store"
    response["Pragma"] = "no-cache"
    response["X-Content-Type-Options"] = "nosniff"
    return response


class FinancialPagination(PageNumberPagination):
    page_size = 50


class ResearchFinanceMixin:
    @action(
        detail=True, methods=["get", "post"], url_path="operations-financieres",
        permission_classes=[ResearchAccess],
    )
    def operations_financieres(self, request, pk=None):
        project = self.get_object()
        if request.method == "POST":
            operation, version, replayed = post_financial_operation(request, project, request.data)
            return _private(Response({
                "operation": FinancialOperationSerializer(operation).data,
                "version": version,
                "replayed": replayed,
            }, status=200 if replayed else 201))
        with locked_financial_project(request, project) as project:
            ledger = reconciled_ledger(project)
            paginator = FinancialPagination()
            page = paginator.paginate_queryset(list(reversed(ledger.operations.values())), request, view=self)
            return _private(paginator.get_paginated_response(FinancialOperationSerializer(page, many=True).data))

    @action(
        detail=True, methods=["get"], url_path=r"justificatifs/(?P<operation_id>[0-9a-f-]+)",
        permission_classes=[ResearchAccess],
    )
    def justificatifs(self, request, pk=None, operation_id=None):
        project = self.get_object()
        with locked_financial_project(request, project) as project:
            ledger = reconciled_ledger(project)
            operation = next((row for key, row in ledger.operations.items() if str(key) == operation_id), None)
            if operation is None:
                raise NotFound("Opération introuvable dans ce projet.")
            if not valid_proof_path(operation):
                raise ResearchConflict("Emplacement du justificatif incohérent.")
            try:
                proof = operation.justificatif.storage.open(operation.justificatif.name, "rb")
            except OSError as exc:
                raise ResearchConflict("Justificatif financier indisponible.") from exc
            try:
                if proof.size != operation.justificatif_taille or hash_uploaded_file(proof) != operation.justificatif_sha256:
                    raise ResearchConflict("Intégrité du justificatif financier non vérifiée.")
                proof.seek(0)
                content_type = {
                    ".pdf": "application/pdf", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                }[Path(operation.justificatif.name).suffix]
                return _private(FileResponse(
                    proof, as_attachment=True, filename=operation.justificatif_nom, content_type=content_type,
                ))
            except Exception:
                proof.close()
                raise

    @action(detail=True, methods=["get"], url_path="rapport-financier", permission_classes=[ResearchAccess])
    def rapport_financier(self, request, pk=None):
        project = self.get_object()
        with locked_financial_project(request, project) as project:
            return _private(Response(report_from_ledger(project, reconciled_ledger(project))))

    @action(
        detail=True, methods=["get"], url_path="exporter-rapport-financier", permission_classes=[ResearchAccess],
    )
    def exporter_rapport_financier(self, request, pk=None):
        project = self.get_object()
        with locked_financial_project(request, project) as project:
            ledger = reconciled_ledger(project)
            response = HttpResponse(content_type="text/csv; charset=utf-8")
            response["Content-Disposition"] = f'attachment; filename="recherche-finances-{project.pk}.csv"'
            writer = csv.writer(response)

            def row(values):
                writer.writerow([_csv_cell(value) for value in values])

            row(["rapport", "valeur"])
            for key, value in report_from_ledger(project, ledger).items():
                row([key, value])
            row([])
            row([
                "operation_id", "type", "montant", "devise", "reference", "date_operation", "libelle",
                "engagement", "contrepassation_de", "created_at", "justificatif_nom", "justificatif_sha256",
                "sequence", "compte", "debit", "credit",
            ])
            for operation in ledger.operations.values():
                values = [
                    str(operation.pk), operation.type, money(operation.montant), "EUR", operation.reference,
                    operation.date_operation.isoformat(), operation.libelle,
                    str(operation.engagement_id or ""), str(operation.contrepassation_de_id or ""),
                    operation.created_at.isoformat(), operation.justificatif_nom, operation.justificatif_sha256,
                    operation.sequence,
                ]
                lines = list(operation.lignes.all())
                if not lines:
                    row([*values, "", "", ""])
                for line in lines:
                    row([*values, line.compte, money(line.debit), money(line.credit)])
            return _private(response)
