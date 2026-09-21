from types import ModuleType
from unittest.mock import patch

from django.test import SimpleTestCase

from sis_common.official_documents import render_official_pdf, tenant_identity_rows


class OfficialDocumentsTests(SimpleTestCase):
    def test_tenant_identity_rows_include_institution_metadata(self):
        request = type(
            "Request",
            (),
            {
                "tenant": type(
                    "Tenant",
                    (),
                    {
                        "nom": "Université Horizon",
                        "type": "universite",
                        "get_type_display": lambda self: "Université",
                    },
                )()
            },
        )()

        rows = tenant_identity_rows(request, "Relevé", serial="REL-01", issue_date="2026-09-21")

        assert ("Établissement", "Université Horizon") in rows
        assert ("Type d'établissement", "Université") in rows
        assert ("Numéro / série", "REL-01") in rows

    def test_render_official_pdf_streams_pdf_response(self):
        fake_module = ModuleType("weasyprint")

        class FakeHTML:
            def __init__(self, string):
                self.string = string

            def write_pdf(self, response):
                response.write(b"%PDF-test")

        fake_module.HTML = FakeHTML

        with patch.dict("sys.modules", {"weasyprint": fake_module}):
            response = render_official_pdf(
                "document.pdf",
                "Document officiel",
                [("Établissement", "Institut")],
                [{"title": "Section", "rows": [("Champ", "Valeur")]}],
                footer_rows=[("Signé", "Oui")],
            )

        assert response.status_code == 200
        assert response["Content-Disposition"] == 'attachment; filename="document.pdf"'
        assert response.content == b"%PDF-test"
