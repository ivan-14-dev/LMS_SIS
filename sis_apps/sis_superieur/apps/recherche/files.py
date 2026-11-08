"""Private research evidence, with read-only access to unchanged legacy uploads."""

import logging
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import SuspiciousFileOperation
from django.core.files.storage import FileSystemStorage
from django.db import connection
from django.http import FileResponse, Http404
from django.utils.deconstruct import deconstructible
from django.utils.text import get_valid_filename

from sis_common.exam_files import PrivateExamStorage

logger = logging.getLogger(__name__)


def safe_parts(name):
    if not isinstance(name, str) or "\\" in name:
        raise SuspiciousFileOperation("Nom de fichier non autorisé.")
    parts = name.split("/")
    if len(parts) < 2 or any(part in ("", ".", "..") for part in parts):
        raise SuspiciousFileOperation("Nom de fichier non autorisé.")
    return parts


@deconstructible
class PrivatePublicationStorage(PrivateExamStorage):
    def _open(self, name, mode="rb"):
        parts = safe_parts(name)
        legacy = parts[0] == "publications"
        private = len(parts) == 4 and parts[:3] == [
            "recherche", connection.schema_name, "publications",
        ]
        if not (legacy or private):
            raise SuspiciousFileOperation("Fichier hors du périmètre de recherche.")
        private_root = Path(self.location).resolve().joinpath(*(parts[:1] if legacy else parts[:3]))
        if not Path(self.path(name)).resolve().is_relative_to(private_root):
            raise SuspiciousFileOperation("Fichier hors du stockage de recherche.")
        try:
            return super()._open(name, mode)
        except FileNotFoundError as error:
            if mode != "rb" or not legacy:
                raise
            storage = FileSystemStorage(location=settings.MEDIA_ROOT)
            # Resolve symlinks as well as lexical traversal before the legacy fallback.
            root = Path(storage.location).resolve() / "publications"
            resolved = Path(storage.path(name)).resolve()
            if not resolved.is_relative_to(root):
                raise SuspiciousFileOperation("Fichier hors du répertoire publications.") from error
            return storage.open(name, mode)


def publication_upload_to(instance, filename):
    return f"recherche/{connection.schema_name}/publications/{uuid4().hex}.pdf"


def delivery_upload_to(instance, filename):
    return f"recherche/{connection.schema_name}/livrables/{uuid4().hex}.pdf"


def original_filename(upload):
    return get_valid_filename(Path(upload.name.replace("\\", "/")).name)[:255] or "document.pdf"


def private_response(field, *, filename=None, delivery=False):
    if not field:
        raise Http404("Fichier indisponible.")
    try:
        if delivery:
            parts = safe_parts(field.name)
            if len(parts) != 4 or parts[:3] != ["recherche", connection.schema_name, "livrables"]:
                raise SuspiciousFileOperation("Fichier hors du périmètre de recherche.")
            root = Path(field.storage.location).resolve().joinpath(*parts[:3])
            if not Path(field.path).resolve().is_relative_to(root):
                raise SuspiciousFileOperation("Fichier hors du stockage de recherche.")
        stream = field.open("rb")
    except (FileNotFoundError, SuspiciousFileOperation) as error:
        raise Http404("Fichier indisponible.") from error
    response = FileResponse(
        stream, as_attachment=True, filename=filename or Path(field.name).name,
        content_type="application/pdf" if Path(field.name).suffix.lower() == ".pdf" else "application/octet-stream",
    )
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


def cleanup_new_file(field, old_name=""):
    """Only remove a file newly written by this command, never the historical file."""
    if field and field.name != old_name and getattr(field, "_committed", False):
        try:
            field.storage.delete(field.name)
        except OSError:
            logger.exception("Impossible de supprimer un nouveau fichier de recherche après échec.")
