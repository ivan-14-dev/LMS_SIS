"""Helpers for strict Excel import/export flows."""

import csv
from datetime import datetime
from io import BytesIO, StringIO
from itertools import islice
from xml.etree.ElementTree import ParseError
from zipfile import BadZipFile, ZipFile

from django.http import HttpResponse
from rest_framework.exceptions import ValidationError

FORMULA_PREFIXES = ("=", "+", "-", "@")


def load_learner_rows(uploaded_file, headers):
    """Read bounded CSV/XLSX learner imports without executing workbook formulas."""
    if uploaded_file.size > 5 * 1024 * 1024:
        raise ValidationError({"file": "La taille maximale est de 5 Mo."})
    filename = uploaded_file.name.lower()
    if filename.endswith(".csv"):
        try:
            rows = list(islice(csv.reader(StringIO(uploaded_file.read().decode("utf-8-sig"))), 1002))
        except (UnicodeDecodeError, csv.Error) as exc:
            raise ValidationError({"file": "Le CSV doit être encodé en UTF-8 et séparé par des virgules."}) from exc
    elif filename.endswith(".xlsx"):
        from openpyxl import load_workbook
        from openpyxl.utils.exceptions import InvalidFileException

        data = uploaded_file.read()
        try:
            with ZipFile(BytesIO(data)) as archive:
                if sum(item.file_size for item in archive.infolist()) > 20 * 1024 * 1024:
                    raise ValidationError({"file": "Le classeur décompressé dépasse 20 Mo."})
            workbook = load_workbook(BytesIO(data), read_only=True, data_only=False)
            try:
                rows = []
                for row in workbook.active.iter_rows():
                    if any(cell.data_type == "f" for cell in row):
                        raise ValidationError({"file": "Les formules Excel ne sont pas acceptées."})
                    rows.append([cell.value for cell in row])
                    if len(rows) > 1001:
                        raise ValidationError({"file": "Importez au maximum 1 000 lignes par fichier."})
            finally:
                workbook.close()
        except (BadZipFile, InvalidFileException, KeyError, ValueError, ParseError) as exc:
            raise ValidationError({"file": "Classeur Excel invalide."}) from exc
    else:
        raise ValidationError({"file": "Utilisez un fichier .csv ou .xlsx."})
    if not rows or _normalized_headers(rows[0]) != headers:
        raise ValidationError({"columns": f"Colonnes attendues : {', '.join(headers)}."})
    if len(rows) > 1001:
        raise ValidationError({"file": "Importez au maximum 1 000 lignes par fichier."})
    result = []
    for number, values in enumerate(rows[1:], 2):
        if all(value in (None, "") for value in values):
            continue
        if len(values) != len(headers):
            raise ValidationError({"file": f"La ligne {number} ne contient pas le bon nombre de colonnes."})
        values = [
            value.date() if header == "date_naissance" and isinstance(value, datetime) else value
            for header, value in zip(headers, values)
        ]
        result.append(
            (
                number,
                {header: value.strip() if isinstance(value, str) else value for header, value in zip(headers, values)},
            )
        )
    return result


def _normalized_headers(headers):
    return [str(header or "").strip() for header in headers]


def _reject_formula_like_value(value, field_name):
    if isinstance(value, str) and value.lstrip().startswith(FORMULA_PREFIXES):
        raise ValidationError({field_name: "Les formules et expressions dynamiques ne sont pas autorisées."})


def _load_xlsx_rows(uploaded_file):
    try:
        from openpyxl import load_workbook
    except ImportError as exc:
        raise ValidationError({"file": "Le support des imports Excel (.xlsx) n'est pas disponible."}) from exc
    workbook = load_workbook(filename=BytesIO(uploaded_file.read()), read_only=True, data_only=True)
    worksheet = workbook.active
    return [list(row) for row in worksheet.iter_rows(values_only=True)]


def _load_xls_rows(uploaded_file):
    try:
        import xlrd
    except ImportError as exc:
        raise ValidationError({"file": "Le support des imports Excel (.xls) n'est pas disponible."}) from exc
    workbook = xlrd.open_workbook(file_contents=uploaded_file.read())
    sheet = workbook.sheet_by_index(0)
    return [sheet.row_values(index) for index in range(sheet.nrows)]


def load_excel_rows(uploaded_file, expected_headers):
    filename = getattr(uploaded_file, "name", "").lower()
    if filename.endswith(".xlsx"):
        rows = _load_xlsx_rows(uploaded_file)
    elif filename.endswith(".xls"):
        rows = _load_xls_rows(uploaded_file)
    else:
        raise ValidationError({"file": "Seuls les fichiers .xlsx et .xls sont autorisés."})
    if not rows:
        raise ValidationError({"file": "Le fichier importé est vide."})
    headers = _normalized_headers(rows[0])
    expected = _normalized_headers(expected_headers)
    if headers != expected:
        raise ValidationError({"columns": ("Les colonnes attendues sont: {}.".format(", ".join(expected)))})
    normalized_rows = []
    for row_number, raw_row in enumerate(rows[1:], start=2):
        values = list(raw_row[: len(expected)]) + [None] * max(0, len(expected) - len(raw_row))
        if all(value in (None, "") for value in values):
            continue
        row = {}
        for index, header in enumerate(expected):
            value = values[index]
            if isinstance(value, str):
                value = value.strip()
                _reject_formula_like_value(value, header)
            row[header] = value
        row["__row_number__"] = row_number
        normalized_rows.append(row)
    return normalized_rows


def template_response(headers, filename, sample_row=None):
    try:
        from openpyxl import Workbook
    except ImportError as exc:
        raise ValidationError({"format": "Le support Excel (.xlsx) n'est pas disponible."}) from exc
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.append(headers)
    if sample_row:
        worksheet.append(sample_row)
    stream = BytesIO()
    workbook.save(stream)
    response = HttpResponse(
        stream.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
