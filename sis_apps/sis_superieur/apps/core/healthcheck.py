"""Healthcheck et monitoring endpoints."""

import time

from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET


@csrf_exempt
@require_GET
def health(request):
    """
    Endpoint de healthcheck basique.

    Retourne 200 si l'application répond.
    Utilisé par les load balancers et Kubernetes liveness probes.
    """
    return JsonResponse(
        {
            "status": "healthy",
            "timestamp": time.time(),
        }
    )


@csrf_exempt
@require_GET
def ready(request):
    """
    Endpoint de readiness check.

    Vérifie que tous les services dépendants sont accessibles:
    - Base de données PostgreSQL
    - Cache Redis

    Utilisé par Kubernetes readiness probes.
    """
    checks = {
        "database": False,
        "cache": False,
    }
    errors = []

    # Check database
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        checks["database"] = True
    except Exception as e:
        errors.append(f"database: {str(e)}")

    # Check cache
    try:
        cache.set("healthcheck", "ok", 10)
        if cache.get("healthcheck") == "ok":
            checks["cache"] = True
        else:
            errors.append("cache: unable to read back value")
    except Exception as e:
        errors.append(f"cache: {str(e)}")

    all_healthy = all(checks.values())

    response_data = {
        "status": "ready" if all_healthy else "not_ready",
        "checks": checks,
        "timestamp": time.time(),
    }

    if errors:
        response_data["errors"] = errors

    return JsonResponse(response_data, status=200 if all_healthy else 503)


@csrf_exempt
@require_GET
def metrics(request):
    """
    Endpoint de métriques basiques.

    Peut être étendu avec prometheus_client pour des métriques plus détaillées.
    """
    from apps.integration.models import EdxEnrollment, EdxUserMapping, OutboxEvent
    from django.contrib.auth import get_user_model

    User = get_user_model()

    return JsonResponse(
        {
            "users_total": User.objects.count(),
            "users_active": User.objects.filter(is_active=True).count(),
            "edx_mappings": EdxUserMapping.objects.filter(actif=True).count(),
            "edx_enrollments_active": EdxEnrollment.objects.filter(
                is_active=True
            ).count(),
            "outbox_pending": OutboxEvent.objects.filter(statut="pending").count(),
            "outbox_failed": OutboxEvent.objects.filter(statut="failed").count(),
            "outbox_dead": OutboxEvent.objects.filter(statut="dead").count(),
            "timestamp": time.time(),
        }
    )
