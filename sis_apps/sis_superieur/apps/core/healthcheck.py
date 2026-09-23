"""Healthcheck et monitoring endpoints."""

import time

from django.core.cache import cache
from django.db import connection
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Gauge, generate_latest


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
    Endpoint de métriques au format d'exposition Prometheus (text/plain).

    Un ``CollectorRegistry`` dédié est construit à chaque requête (plutôt
    qu'un registre global par défaut) afin d'éviter tout état partagé entre
    workers ou entre tests, et de garantir des valeurs toujours à jour issues
    de la base de données.
    """
    from apps.integration.models import EdxEnrollment, EdxUserMapping, OutboxEvent
    from django.contrib.auth import get_user_model

    User = get_user_model()

    registry = CollectorRegistry()

    users_total = Gauge("sis_users_total", "Nombre total d'utilisateurs", registry=registry)
    users_total.set(User.objects.count())

    users_active = Gauge("sis_users_active", "Nombre d'utilisateurs actifs", registry=registry)
    users_active.set(User.objects.filter(is_active=True).count())

    edx_mappings = Gauge("sis_edx_mappings_active", "Nombre de mappings EDX actifs", registry=registry)
    edx_mappings.set(EdxUserMapping.objects.filter(actif=True).count())

    edx_enrollments = Gauge(
        "sis_edx_enrollments_active", "Nombre d'inscriptions EDX actives", registry=registry
    )
    edx_enrollments.set(EdxEnrollment.objects.filter(is_active=True).count())

    outbox_pending = Gauge("sis_outbox_events_pending", "Événements outbox en attente", registry=registry)
    outbox_pending.set(OutboxEvent.objects.filter(statut="pending").count())

    outbox_failed = Gauge("sis_outbox_events_failed", "Événements outbox en échec", registry=registry)
    outbox_failed.set(OutboxEvent.objects.filter(statut="failed").count())

    outbox_dead = Gauge(
        "sis_outbox_events_dead", "Événements outbox définitivement en échec", registry=registry
    )
    outbox_dead.set(OutboxEvent.objects.filter(statut="dead").count())

    scrape_timestamp = Gauge(
        "sis_metrics_scrape_timestamp_seconds",
        "Horodatage Unix de la génération des métriques",
        registry=registry,
    )
    scrape_timestamp.set(time.time())

    return HttpResponse(generate_latest(registry), content_type=CONTENT_TYPE_LATEST)
