from io import BytesIO
from unittest.mock import patch
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from openpyxl import Workbook
from rest_framework.exceptions import ValidationError

from sis_common.spreadsheets import load_excel_rows


class SpreadsheetImportTests(SimpleTestCase):
    def test_xlsx_formula_in_numeric_column_is_rejected(self):
        workbook = Workbook()
        workbook.active.append(["epreuve_id", "eleve_matricule", "note"])
        workbook.active.append([1, "MAT-001", "=SUM(8, 7)"])
        stream = BytesIO()
        workbook.save(stream)
        uploaded_file = SimpleUploadedFile("resultats.xlsx", stream.getvalue())

        with pytest.raises(ValidationError, match="formules"):
            load_excel_rows(uploaded_file, ["epreuve_id", "eleve_matricule", "note"])

    def test_invalid_xlsx_is_reported_as_validation_error(self):
        uploaded_file = SimpleUploadedFile("resultats.xlsx", b"not a workbook")

        with pytest.raises(ValidationError, match="invalide"):
            load_excel_rows(uploaded_file, ["epreuve_id", "eleve_matricule", "note"])

    def test_invalid_xls_is_reported_as_validation_error(self):
        uploaded_file = SimpleUploadedFile("resultats.xls", b"not a workbook")

        with pytest.raises(ValidationError, match="invalide"):
            load_excel_rows(uploaded_file, ["epreuve_id", "eleve_matricule", "note"])

    def test_compressed_xlsx_beyond_limit_is_rejected(self):
        stream = BytesIO()
        with ZipFile(stream, "w", compression=ZIP_DEFLATED) as archive:
            archive.writestr("xl/worksheets/sheet1.xml", b" " * (20 * 1024 * 1024 + 1))
        uploaded_file = SimpleUploadedFile("resultats.xlsx", stream.getvalue())

        with pytest.raises(ValidationError, match="décompressé"):
            load_excel_rows(uploaded_file, ["epreuve_id", "eleve_matricule", "note"])

    @patch("sis_common.spreadsheets._load_xlsx_rows")
    def test_load_excel_rows_requires_exact_headers(self, mocked_loader):
        mocked_loader.return_value = [["epreuve_id", "eleve_matricule"], [1, "MAT-001"]]
        uploaded_file = type("File", (), {"name": "resultats.xlsx", "read": lambda self: b""})()

        with pytest.raises(ValidationError):
            load_excel_rows(
                uploaded_file,
                ["epreuve_id", "eleve_matricule", "note"],
            )

    @patch("sis_common.spreadsheets._load_xlsx_rows")
    def test_load_excel_rows_rejects_formula_like_values(self, mocked_loader):
        mocked_loader.return_value = [
            ["epreuve_id", "eleve_matricule", "note"],
            [1, "=cmd()", 10],
        ]
        uploaded_file = type("File", (), {"name": "resultats.xlsx", "read": lambda self: b""})()

        with pytest.raises(ValidationError):
            load_excel_rows(uploaded_file, ["epreuve_id", "eleve_matricule", "note"])
