"""Current-tenant boundary for LMS integration endpoints."""

from django.db import connection
from django_tenants.utils import get_public_schema_name, get_tenant_model
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAdminUser


def lms_schema_tenant_id():
    """Resolve the actual schema owner, including inside background schema_context tasks."""
    schema = connection.schema_name
    if not schema or schema == get_public_schema_name():
        raise ValueError("Un établissement courant valide est requis.")
    tenant_id = get_tenant_model().objects.filter(schema_name=schema).values_list("pk", flat=True).first()
    if tenant_id is None:
        raise ValueError("Un établissement courant valide est requis.")
    return tenant_id


def current_lms_tenant(request):
    tenant = getattr(request, "tenant", None)
    schema = getattr(tenant, "schema_name", None)
    tenant_id = getattr(tenant, "pk", None)
    if (
        tenant_id is None
        or not schema
        or schema == get_public_schema_name()
        or schema != getattr(connection, "schema_name", None)
        or tenant_id != getattr(getattr(connection, "tenant", None), "pk", None)
        or not request.user.is_active
        or getattr(request.user, "etablissement_id", None) not in (None, tenant_id)
    ):
        raise PermissionDenied("Un établissement courant valide est requis.")
    return tenant


class IsCurrentLmsTenantAdmin(IsAdminUser):
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        current_lms_tenant(request)
        return True
