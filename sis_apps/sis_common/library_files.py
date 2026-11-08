"""Private library PDFs, retaining read access to unmoved legacy files."""

from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.db import connection
from django.utils.deconstruct import deconstructible

from sis_common.exam_files import PrivateExamStorage


@deconstructible
class PrivateLibraryStorage(PrivateExamStorage):
    def _open(self, name, mode="rb"):
        try:
            return super()._open(name, mode)
        except FileNotFoundError:
            # Only the historical upload directory may fall back to MEDIA_ROOT.
            path = Path(name)
            parts = path.parts
            if (
                mode != "rb"
                or path.is_absolute()
                or len(parts) < 3
                or ".." in parts
                or parts[:2] != ("bibliotheque", "numerique")
            ):
                raise
            return FileSystemStorage(location=settings.MEDIA_ROOT).open(name, mode)


def library_upload_to(instance, filename):
    return f"bibliotheque/numerique/{connection.schema_name}/{uuid4().hex}{Path(filename).suffix.lower()}"
