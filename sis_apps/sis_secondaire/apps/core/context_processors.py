"""Context processors pour les templates."""

from .middleware import get_current_request_id, get_current_tenant_id


def tenant_context(request):
    return {
        "request_id": get_current_request_id(),
        "tenant_id": get_current_tenant_id(),
        "app_name": "SIS Secondaire",
    }
