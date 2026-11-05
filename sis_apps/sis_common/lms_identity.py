"""Opaque LMS identifiers independent of tenant-local primary keys."""

from base64 import b32encode
from uuid import uuid5


def lms_username(user):
    return "sis_" + b32encode(user.integration_id.bytes).decode("ascii").rstrip("=").lower()


def lms_course_number(source, *, namespace=None):
    identifier = source.integration_id
    if namespace is not None:
        identifier = uuid5(namespace.integration_id, str(identifier))
    return "sis_" + b32encode(identifier.bytes).decode("ascii").rstrip("=").lower()
