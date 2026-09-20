import hashlib
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import SuspiciousFileOperation, ValidationError
from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible


@deconstructible
class PrivateExamStorage(FileSystemStorage):
    """Stockage local sans URL publique pour les copies d'examen."""

    def __init__(self, location=None):
        super().__init__(
            location=location
            or getattr(
                settings,
                "PRIVATE_EXAM_STORAGE_ROOT",
                settings.BASE_DIR / "private_exam_copies",
            ),
            base_url=None,
        )

    def url(self, name):
        raise SuspiciousFileOperation(
            "Les copies d'examen ne disposent pas d'URL publique."
        )


@deconstructible
class PrivateFinancialStorage(FileSystemStorage):
    """Stockage local privé pour les justificatifs financiers."""

    def __init__(self, location=None):
        super().__init__(
            location=location
            or getattr(
                settings,
                "PRIVATE_FINANCIAL_STORAGE_ROOT",
                settings.BASE_DIR / "private_financial_documents",
            ),
            base_url=None,
        )

    def url(self, name):
        raise SuspiciousFileOperation(
            "Les justificatifs financiers ne disposent pas d'URL publique."
        )


def exam_copy_upload_to(instance, filename):
    extension = Path(filename).suffix.lower()
    return f"examens/{instance.convocation.epreuve_id}/{uuid4().hex}{extension}"


def validate_exam_copy(file):
    max_size = getattr(settings, "EXAM_COPY_MAX_SIZE", 25 * 1024 * 1024)
    if file.size > max_size:
        raise ValidationError(
            f"La copie dépasse la taille maximale autorisée de {max_size // (1024 * 1024)} Mo."
        )
    if Path(file.name).suffix.lower() != ".pdf":
        raise ValidationError("Seules les copies PDF sont autorisées.")
    if getattr(file, "content_type", "application/pdf") not in (
        "application/pdf",
        "application/x-pdf",
        "application/octet-stream",
    ):
        raise ValidationError("Le type MIME du fichier ne correspond pas à un PDF.")

    position = file.tell()
    file.seek(0)
    signature = file.read(5)
    file.seek(position)
    if signature != b"%PDF-":
        raise ValidationError("Le contenu du fichier ne correspond pas à un PDF.")


def hash_uploaded_file(file):
    digest = hashlib.sha256()
    position = file.tell()
    file.seek(0)
    for chunk in file.chunks():
        digest.update(chunk)
    file.seek(position)
    return digest.hexdigest()


def payment_proof_upload_to(instance, filename):
    extension = Path(filename).suffix.lower()
    return f"paiements/{instance.facture_id}/{uuid4().hex}{extension}"


def validate_payment_proof(file):
    max_size = getattr(settings, "PAYMENT_PROOF_MAX_SIZE", 10 * 1024 * 1024)
    if file.size > max_size:
        raise ValidationError("Le justificatif de paiement dépasse la taille autorisée.")
    extension = Path(file.name).suffix.lower()
    signatures = {
        ".pdf": (b"%PDF-",),
        ".png": (b"\x89PNG\r\n\x1a\n",),
        ".jpg": (b"\xff\xd8\xff",),
        ".jpeg": (b"\xff\xd8\xff",),
    }
    if extension not in signatures:
        raise ValidationError("Le justificatif doit être un PDF, PNG ou JPEG.")
    position = file.tell()
    file.seek(0)
    header = file.read(8)
    file.seek(position)
    if not any(header.startswith(signature) for signature in signatures[extension]):
        raise ValidationError("Le contenu du justificatif ne correspond pas à son format.")
