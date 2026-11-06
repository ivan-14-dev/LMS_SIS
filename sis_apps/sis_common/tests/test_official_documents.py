import base64
import hashlib
import json
import uuid
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, patch

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from django.urls import resolve
from rest_framework.test import APIRequestFactory

from sis_common.official_documents import render_official_pdf, tenant_identity_rows, verify_official_archive


def issued_archive():
    pdf = b"%PDF-1.7 issued document"
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key().public_bytes_raw()
    encoded_key = base64.b64encode(public_key).decode("ascii")
    archive_id = uuid.uuid4()
    digest = hashlib.sha256(pdf).hexdigest()
    manifest = {
        "archive": str(archive_id),
        "version": 1,
        "etablissement": 1,
        "sha256": digest,
        "empreinte_cle": hashlib.sha256(public_key).hexdigest(),
        "beneficiaire": "private-identity",
    }
    proof = base64.b64encode(
        private_key.sign(json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode())
    ).decode("ascii")
    archive = SimpleNamespace(
        pk=archive_id,
        version=1,
        etablissement_id=1,
        sha256=digest,
        manifeste=manifest,
        preuve=proof,
        cle_publique=encoded_key,
        signature=SimpleNamespace(cle_publique=encoded_key),
    )
    return archive, pdf


class OfficialDocumentsTests(SimpleTestCase):
    def test_minimal_archive_verification_distinguishes_current_revoked_and_tampered_without_identity(self):
        archive, pdf = issued_archive()
        assert verify_official_archive(archive, pdf) == {"valide": True}
        assert verify_official_archive(archive, pdf + b" altered") == {"valide": False}
        assert verify_official_archive(SimpleNamespace(**{**vars(archive), "preuve": "invalid"}), pdf) == {
            "valide": False
        }
        assert verify_official_archive(SimpleNamespace(**{**vars(archive), "revocation": object()}), pdf) == {
            "valide": False
        }
        assert verify_official_archive(SimpleNamespace(**{**vars(archive), "pk": uuid.uuid4()}), pdf) == {
            "valide": False
        }
        assert verify_official_archive(None, pdf) == {"valide": False}
        assert verify_official_archive(archive, None) == {"valide": False}

    def test_anonymous_http_verification_requires_presented_pdf_and_matching_tenant(self):
        archive, pdf = issued_archive()
        url = "/api/v1/core/documents-signes/verification-publique/"
        view = resolve(url).func
        assert view.actions == {"post": "verification_publique"}
        factory = APIRequestFactory()

        def verify(tenant_id=1, content=pdf, with_pdf=True):
            payload = {"archive_id": str(archive.pk)}
            if with_pdf:
                payload["pdf"] = SimpleUploadedFile("document.pdf", content, content_type="application/pdf")
            request = factory.post(url, payload, format="multipart")
            request.tenant = SimpleNamespace(pk=tenant_id, schema_name="fast_test")
            return view(request)

        def scoped_lookup(**filters):
            queryset = MagicMock()
            queryset.select_related.return_value.defer.return_value.first.return_value = (
                archive if filters == {"pk": archive.pk, "etablissement_id": archive.etablissement_id} else None
            )
            return queryset

        with (
            patch("sis_common.signed_documents.Archive.objects.filter", side_effect=scoped_lookup) as filter_archive,
            patch("sis_common.signed_documents.SignedDocumentViewSet.get_throttles", return_value=[]),
        ):
            response = verify()
            assert response.status_code == 200
            assert response.data == {"valide": True}
            assert response["Cache-Control"] == "no-store"
            assert verify(content=pdf + b" altered").data == {"valide": False}
            assert verify(tenant_id=2).data == {"valide": False}
            assert verify(with_pdf=False).data == {"valide": False}
            with patch("sis_common.signed_documents.MAX_PUBLIC_VERIFICATION_PDF_BYTES", len(pdf) - 1):
                assert verify().data == {"valide": False}
            archive.revocation = object()
            assert verify().data == {"valide": False}
            filter_archive.assert_any_call(pk=archive.pk, etablissement_id=2)

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

            def write_pdf(self, response, *, presentational_hints):
                assert presentational_hints is False
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

    def test_supported_pdf_engine_renders_a_real_document(self):
        response = render_official_pdf(
            "verification.pdf",
            "Document de verification",
            [("Institution", "Test")],
            [{"title": "Resultat", "rows": [("Evaluation", "12/20")]}],
        )
        assert response.content.startswith(b"%PDF-")
        assert len(response.content) > 1000
