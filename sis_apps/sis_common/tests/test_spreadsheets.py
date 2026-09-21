from unittest.mock import patch

import pytest
from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError

from sis_common.spreadsheets import load_excel_rows


class SpreadsheetImportTests(SimpleTestCase):
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
