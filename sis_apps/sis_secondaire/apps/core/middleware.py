"""Middleware pour audit, tenant context, request_id."""

import threading
import time
import uuid

_local = threading.local()


def get_current_request_id():
    return getattr(_local, "request_id", None)


def get_current_tenant_id():
    return getattr(_local, "tenant_id", None)


class RequestIdMiddleware:
    """Injecte un request_id unique dans chaque requête."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        _local.request_id = request_id
        request.request_id = request_id
        response = self.get_response(request)
        response["X-Request-ID"] = request_id
        return response


class AuditLogMiddleware:
    """Log toutes les requêtes (méthode, path, status, durée)."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.logger = __import__("logging").getLogger("apps.audit")

    def __call__(self, request):
        start = time.time()
        response = self.get_response(request)
        duration = (time.time() - start) * 1000
        if request.path.startswith("/api/"):
            self.logger.info(
                "API call",
                extra={
                    "method": request.method,
                    "path": request.path,
                    "status": response.status_code,
                    "duration_ms": int(duration),
                    "user_id": (
                        request.user.id if request.user.is_authenticated else None
                    ),
                    "ip": request.META.get("REMOTE_ADDR"),
                },
            )
        return response


class TenantContextMiddleware:
    """Expose le tenant_id courant dans le thread local."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        tenant = getattr(request, "tenant", None)
        _local.tenant_id = tenant.id if tenant else None
        return self.get_response(request)
