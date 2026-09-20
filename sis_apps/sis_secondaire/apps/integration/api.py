"""API views for Open edX integration (SIS Secondaire).

Endpoints :
- POST /webhook/lms/        : webhook entrant LMS
- POST /webhook/cms/        : webhook entrant CMS Studio
- GET  /sync/status/        : état de la synchronisation
- POST /sync/user/<id>/     : force sync d'un utilisateur
- POST /sync/course/        : crée un cours dans CMS
- POST /sync/enroll/        : inscrit un élève à un cours
- POST /sync/grade/         : pousse une note vers LMS
- POST /sync/certificate/   : délivre un certificat
- GET  /health/             : santé LMS + CMS
"""

import logging

from django.conf import settings
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response
from sis_common.webhooks import verify_hmac_signature

from .edx_client import get_edx_client
from .models import EdxCourseMapping, EdxEnrollment, EdxUserMapping, OutboxEvent
from .serializers import (
    EdxCourseMappingSerializer,
    EdxUserMappingSerializer,
    OutboxEventSerializer,
)
from .sync_service import SyncService

logger = logging.getLogger(__name__)


def _verify_hmac(request) -> bool:
    signature = request.headers.get("X-Signature", "")
    return verify_hmac_signature(settings.WEBHOOK_SECRET, request.body, signature)


def _paginated_response(request, queryset, serializer_class):
    paginator = PageNumberPagination()
    page = paginator.paginate_queryset(queryset, request)
    serializer = serializer_class(page, many=True)
    return paginator.get_paginated_response(serializer.data)


# ============== WEBHOOKS ENTRANTS ==============


@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def webhook_lms(request):
    """Webhook entrant depuis le LMS Open edX."""
    if not _verify_hmac(request):
        return Response(
            {"error": "Invalid signature"}, status=status.HTTP_401_UNAUTHORIZED
        )
    event_type = request.headers.get("X-Event-Type", "")
    payload = request.data
    from .tasks import (
        process_certificate_webhook,
        process_enrollment_webhook,
        process_grade_webhook,
        process_user_webhook,
    )

    if "user" in event_type:
        process_user_webhook.delay(payload)
    elif "enrollment" in event_type:
        process_enrollment_webhook.delay(payload)
    elif "grade" in event_type:
        process_grade_webhook.delay(payload)
    elif "certificate" in event_type:
        process_certificate_webhook.delay(payload)
    else:
        logger.warning(f"Unknown LMS event: {event_type}")
    return Response({"status": "queued", "event": event_type})


@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def webhook_cms(request):
    """Webhook entrant depuis le CMS Studio."""
    if not _verify_hmac(request):
        return Response(
            {"error": "Invalid signature"}, status=status.HTTP_401_UNAUTHORIZED
        )
    event_type = request.headers.get("X-Event-Type", "")
    payload = request.data
    from .tasks import process_course_published, process_xblock_published

    if "xblock" in event_type:
        process_xblock_published.delay(payload)
    elif "course.published" in event_type:
        process_course_published.delay(payload)
    else:
        logger.info(f"CMS event {event_type} ack")
    return Response({"status": "queued", "event": event_type})


# ============== SYNCHRONISATION ==============


@api_view(["GET"])
@permission_classes([IsAdminUser])
def sync_status(request):
    from django.db.models import Count

    outbox_counts = OutboxEvent.objects.values("statut").annotate(n=Count("id"))
    enrollments_count = EdxEnrollment.objects.filter(is_active=True).count()
    mappings_count = EdxUserMapping.objects.filter(actif=True).count()
    courses_count = EdxCourseMapping.objects.filter(actif=True).count()
    return Response(
        {
            "outbox": {c["statut"]: c["n"] for c in outbox_counts},
            "enrollments_active": enrollments_count,
            "users_mapped": mappings_count,
            "courses_mapped": courses_count,
        }
    )


@api_view(["GET"])
@permission_classes([IsAdminUser])
def user_mappings(request):
    """Liste paginée des correspondances entre utilisateurs SIS et Open edX."""
    queryset = EdxUserMapping.objects.select_related("user_sis").order_by(
        "-date_sync", "-created_at"
    )
    return _paginated_response(request, queryset, EdxUserMappingSerializer)


@api_view(["GET"])
@permission_classes([IsAdminUser])
def course_mappings(request):
    """Liste paginée des correspondances entre cours SIS et Open edX."""
    queryset = EdxCourseMapping.objects.select_related("matiere", "classe").order_by(
        "course_name"
    )
    return _paginated_response(request, queryset, EdxCourseMappingSerializer)


@api_view(["GET"])
@permission_classes([IsAdminUser])
def outbox_events(request):
    """Liste paginée des événements de synchronisation, filtrable par statut."""
    queryset = OutboxEvent.objects.all()
    statut = request.query_params.get("statut")
    if statut:
        if statut not in dict(OutboxEvent.STATUT_CHOICES):
            return Response(
                {"statut": "Statut invalide."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        queryset = queryset.filter(statut=statut)
    return _paginated_response(request, queryset, OutboxEventSerializer)


@api_view(["POST"])
@permission_classes([IsAdminUser])
def sync_user(request, user_id):
    """Force la synchronisation d'un utilisateur vers le LMS."""
    from apps.utilisateurs.models import Utilisateur

    try:
        user = Utilisateur.objects.get(pk=user_id)
    except Utilisateur.DoesNotExist:
        return Response({"error": "User not found"}, status=404)
    service = SyncService()
    role = request.data.get("role", "student")
    try:
        mapping = service.sync_user_to_lms(user, role=role)
        return Response(
            {
                "status": "ok",
                "username_edx": mapping.username_edx,
                "user_id_edx": mapping.user_id_edx,
            }
        )
    except Exception as e:
        return Response({"error": str(e)}, status=500)


@api_view(["POST"])
@permission_classes([IsAdminUser])
def sync_course(request):
    """Crée un cours dans le CMS Studio à partir d'une matière/classe."""
    from apps.classes.models import Classe, Matiere

    matiere_id = request.data.get("matiere_id")
    classe_id = request.data.get("classe_id")
    try:
        matiere = Matiere.objects.get(pk=matiere_id)
        classe = Classe.objects.get(pk=classe_id)
    except (Matiere.DoesNotExist, Classe.DoesNotExist):
        return Response({"error": "Matiere or Classe not found"}, status=404)
    display_name = request.data.get("display_name", f"{matiere.nom} - {classe.nom}")
    service = SyncService()
    try:
        mapping = service.sync_course_to_cms(matiere, classe, display_name)
        return Response(
            {
                "status": "ok",
                "course_id": mapping.course_id,
                "course_name": mapping.course_name,
            }
        )
    except Exception as e:
        return Response({"error": str(e)}, status=500)


@api_view(["POST"])
@permission_classes([IsAdminUser])
def sync_enroll(request):
    """Inscrit un élève à un cours LMS."""
    from apps.eleves.models import Eleve

    eleve_id = request.data.get("eleve_id")
    course_mapping_id = request.data.get("course_mapping_id")
    mode = request.data.get("mode", "audit")
    try:
        eleve = Eleve.objects.get(pk=eleve_id)
        course_mapping = EdxCourseMapping.objects.get(pk=course_mapping_id)
    except (Eleve.DoesNotExist, EdxCourseMapping.DoesNotExist):
        return Response({"error": "Eleve or Course not found"}, status=404)
    service = SyncService()
    try:
        enrollment = service.sync_enrollment_to_lms(eleve, course_mapping, mode=mode)
        return Response(
            {
                "status": "ok",
                "enrollment_id": enrollment.enrollment_id,
                "is_active": enrollment.is_active,
            }
        )
    except Exception as e:
        return Response({"error": str(e)}, status=500)


@api_view(["POST"])
@permission_classes([IsAdminUser])
def sync_grade(request):
    """Pousse une note vers le LMS."""
    from apps.eleves.models import Eleve

    eleve_id = request.data.get("eleve_id")
    course_mapping_id = request.data.get("course_mapping_id")
    subsection_id = request.data.get("subsection_id")
    score = request.data.get("score")
    max_score = request.data.get("max_score", 20.0)
    try:
        eleve = Eleve.objects.get(pk=eleve_id)
        course_mapping = EdxCourseMapping.objects.get(pk=course_mapping_id)
    except (Eleve.DoesNotExist, EdxCourseMapping.DoesNotExist):
        return Response({"error": "Eleve or Course not found"}, status=404)
    service = SyncService()
    try:
        result = service.sync_grade_to_lms(
            eleve, course_mapping, subsection_id, score, max_score
        )
        return Response({"status": "ok", "result": result})
    except Exception as e:
        return Response({"error": str(e)}, status=500)


@api_view(["POST"])
@permission_classes([IsAdminUser])
def sync_certificate(request):
    """Délivre un certificat LMS."""
    from apps.eleves.models import Eleve

    eleve_id = request.data.get("eleve_id")
    course_mapping_id = request.data.get("course_mapping_id")
    cert_type = request.data.get("certificate_type", "honor")
    try:
        eleve = Eleve.objects.get(pk=eleve_id)
        course_mapping = EdxCourseMapping.objects.get(pk=course_mapping_id)
    except (Eleve.DoesNotExist, EdxCourseMapping.DoesNotExist):
        return Response({"error": "Not found"}, status=404)
    service = SyncService()
    try:
        result = service.sync_certificate_to_lms(eleve, course_mapping, cert_type)
        return Response({"status": "ok", "result": result})
    except Exception as e:
        return Response({"error": str(e)}, status=500)


@api_view(["GET"])
@permission_classes([IsAdminUser])
def health(request):
    client = get_edx_client()
    checks = client.health_check()
    connected = all(
        check if isinstance(check, bool) else check.get("ok", False)
        for check in checks.values()
    )
    return Response(
        {
            **checks,
            "connected": connected,
            "lms_url": settings.EDX_LMS_URL,
            "cms_url": settings.EDX_CMS_URL,
            "oauth_status": "configured",
            "webhook_status": "active",
            "last_check": timezone.now(),
        }
    )
