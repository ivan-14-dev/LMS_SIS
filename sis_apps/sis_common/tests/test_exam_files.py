import tempfile
from pathlib import Path

from django.core.exceptions import SuspiciousFileOperation, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, override_settings
from sis_common.exam_files import (
    PrivateExamStorage,
    PrivateFinancialStorage,
    hash_uploaded_file,
    validate_exam_copy,
    validate_payment_proof,
)


class ExamFileValidationTests(SimpleTestCase):
    @staticmethod
    def pdf(name="copie.pdf", content=b"%PDF-1.7\ncontent"):
        return SimpleUploadedFile(name, content, content_type="application/pdf")

    def test_accepts_pdf_and_preserves_stream_position(self):
        uploaded_file = self.pdf()

        validate_exam_copy(uploaded_file)

        self.assertEqual(uploaded_file.tell(), 0)
        self.assertEqual(
            hash_uploaded_file(uploaded_file),
            "275904d2c62c45e21f420f0e323ec3518a0c6223623ed1f89b9d1ebd9a5ddff3",
        )
        self.assertEqual(uploaded_file.tell(), 0)

    def test_rejects_non_pdf_extension(self):
        with self.assertRaisesMessage(ValidationError, "copies PDF"):
            validate_exam_copy(self.pdf(name="copie.txt"))

    def test_rejects_invalid_pdf_signature(self):
        with self.assertRaisesMessage(ValidationError, "correspond pas à un PDF"):
            validate_exam_copy(self.pdf(content=b"not a pdf"))

    def test_rejects_invalid_content_type(self):
        uploaded_file = SimpleUploadedFile("copie.pdf", b"%PDF-1.7\ncontent", content_type="text/plain")

        with self.assertRaisesMessage(ValidationError, "type MIME"):
            validate_exam_copy(uploaded_file)

    @override_settings(EXAM_COPY_MAX_SIZE=5)
    def test_rejects_oversized_file(self):
        with self.assertRaisesMessage(ValidationError, "taille maximale"):
            validate_exam_copy(self.pdf())


class PrivateExamStorageTests(SimpleTestCase):
    def test_storage_never_exposes_public_url(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = PrivateExamStorage(location=Path(directory))

            with self.assertRaises(SuspiciousFileOperation):
                storage.url("copie.pdf")


class PaymentProofValidationTests(SimpleTestCase):
    def test_accepts_supported_file_signatures(self):
        files = (
            SimpleUploadedFile("preuve.pdf", b"%PDF-1.7\ncontent"),
            SimpleUploadedFile("preuve.png", b"\x89PNG\r\n\x1a\ncontent"),
            SimpleUploadedFile("preuve.jpg", b"\xff\xd8\xffcontent"),
        )

        for uploaded_file in files:
            with self.subTest(name=uploaded_file.name):
                validate_payment_proof(uploaded_file)
                self.assertEqual(uploaded_file.tell(), 0)

    def test_rejects_mismatched_extension_and_content(self):
        uploaded_file = SimpleUploadedFile("preuve.pdf", b"\x89PNG\r\n\x1a\n")

        with self.assertRaisesMessage(ValidationError, "correspond pas"):
            validate_payment_proof(uploaded_file)

    def test_financial_storage_never_exposes_public_url(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = PrivateFinancialStorage(location=Path(directory))

            with self.assertRaises(SuspiciousFileOperation):
                storage.url("preuve.pdf")
