"""API views for Open edX integration (SIS Supérieur)."""

import hashlib
import logging

from django.conf import settings
from django.db.models import Count
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
from .serializers import EdxCourseMappingSerializer, EdxUserMappingSerializer, OutboxEventSerializer
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


@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def webhook_lms(request):
    if not _verify_hmac(request):
        return Response(
            {"error": "Invalid signature"}, status=status.HTTP_401_UNAUTHORIZED
        )
    event_type = request.headers.get("X-Event-Type", "")
    payload = dict(request.data)
    supplied_event_id = request.headers.get("X-Event-ID")
    event_material = (
        supplied_event_id.encode()
        if supplied_event_id
        else event_type.encode() + b":" + request.body
    )
    payload["_event_id"] = hashlib.sha256(event_material).hexdigest()
    schema_name = getattr(getattr(request, "tenant", None), "schema_name", None)
    if not schema_name:
        return Response(
            {"error": "Tenant context is required"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    from .tasks import (
        process_certificate_webhook,
        process_enrollment_webhook,
        process_grade_webhook,
        process_user_webhook,
    )

    if event_type in {
        "user.created",
        "user.updated",
        "org.openedx.learning.user.created.v1",
        "org.openedx.learning.user.updated.v1",
    }:
        process_user_webhook.delay(event_type, payload, schema_name)
    elif event_type in {
        "enrollment.created",
        "enrollment.updated",
        "enrollment.deleted",
        "org.openedx.learning.course.enrollment.created.v1",
        "org.openedx.learning.course.enrollment.changed.v1",
        "org.openedx.learning.course.unenrollment.completed.v1",
        "org.openedx.learning.enrollment.created.v1",
        "org.openedx.learning.enrollment.updated.v1",
        "org.openedx.learning.enrollment.deleted.v1",
    }:
        process_enrollment_webhook.delay(event_type, payload, schema_name)
    elif event_type in {
        "grade.updated",
        "org.openedx.learning.course.persistent_grade_summary.changed.v1",
        "org.openedx.learning.course.grade.updated.v1",
        "org.openedx.learning.course.assessment.grade.changed.v1",
    }:
        process_grade_webhook.delay(event_type, payload, schema_name)
    elif event_type in {
        "certificate.issued",
        "certificate.revoked",
        "org.openedx.learning.certificate.created.v1",
        "org.openedx.learning.certificate.changed.v1",
        "org.openedx.learning.certificate.issued.v1",
        "org.openedx.learning.certificate.revoked.v1",
    }:
        process_certificate_webhook.delay(event_type, payload, schema_name)
    else:
        logger.warning(f"Unknown LMS event: {event_type}")
        return Response(
            {"error": "Unsupported event type", "event": event_type},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return Response({"status": "queued", "event": event_type})


@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def webhook_cms(request):
    if not _verify_hmac(request):
        return Response(
            {"error": "Invalid signature"}, status=status.HTTP_401_UNAUTHORIZED
        )
    event_type = request.headers.get("X-Event-Type", "")
    payload = dict(request.data)
    schema_name = getattr(getattr(request, "tenant", None), "schema_name", None)
    if not schema_name:
        return Response(
            {"error": "Tenant context is required"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    from .tasks import process_cms_webhook

    supported_events = {
        "course.published",
        "course.deleted",
        "xblock.published",
        "asset.uploaded",
        "org.openedx.studio.course.published.v1",
        "org.openedx.studio.course.deleted.v1",
        "org.openedx.studio.xblock.published.v1",
        "org.openedx.studio.asset.uploaded.v1",
    }
    if event_type in supported_events:
        process_cms_webhook.delay(event_type, payload, schema_name)
    else:
        logger.warning(f"Unknown CMS event: {event_type}")
        return Response(
            {"error": "Unsupported event type", "event": event_type},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return Response({"status": "queued", "event": event_type})


@api_view(["GET"])
@permission_classes([IsAdminUser])
def sync_status(request):
    outbox_counts = OutboxEvent.objects.values("statut").annotate(n=Count("id"))
    return Response(
        {
            "outbox": {c["statut"]: c["n"] for c in outbox_counts},
            "enrollments_active": EdxEnrollment.objects.filter(is_active=True).count(),
            "users_mapped": EdxUserMapping.objects.filter(actif=True).count(),
            "courses_mapped": EdxCourseMapping.objects.filter(actif=True).count(),
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
    queryset = EdxCourseMapping.objects.select_related("ecue").order_by("course_name")
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
    from apps.etablissement.models import AnneeUniversitaire
    from apps.ue_ecue.models import ECUE

    ecue_id = request.data.get("ecue_id")
    annee_id = request.data.get("annee_id")
    try:
        ecue = ECUE.objects.get(pk=ecue_id)
        annee = AnneeUniversitaire.objects.get(pk=annee_id)
    except (ECUE.DoesNotExist, AnneeUniversitaire.DoesNotExist):
        return Response({"error": "Not found"}, status=404)
    display_name = request.data.get("display_name", f"{ecue.nom} - {annee.libelle}")
    service = SyncService()
    try:
        mapping = service.sync_course_to_cms(ecue, annee, display_name)
        return Response({"status": "ok", "course_id": mapping.course_id})
    except Exception as e:
        return Response({"error": str(e)}, status=500)


@api_view(["POST"])
@permission_classes([IsAdminUser])
def sync_course_live(request, mapping_id):
    """Active BigBlueButton sur un cours Open edX déjà mappé."""
    try:
        mapping = EdxCourseMapping.objects.get(pk=mapping_id, actif=True)
    except EdxCourseMapping.DoesNotExist:
        return Response({"error": "Course mapping not found"}, status=404)

    tenant = getattr(request, "tenant", None)
    live_configuration = getattr(tenant, "configuration_visio", {})
    features = getattr(tenant, "fonctionnalites", {})
    provider = live_configuration.get("provider", "none")
    if not features.get("classes_virtuelles", False):
        return Response(
            {"error": "Virtual classrooms are disabled for this establishment."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if provider != "bigbluebutton":
        return Response(
            {"error": "BigBlueButton must be selected in establishment settings."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        client = get_edx_client()
        providers = client.get_course_live_providers(mapping.course_id)
        available = providers.get("providers", {}).get("available", {})
        if "big_blue_button" not in available:
            return Response(
                {"error": "BigBlueButton is not configured in Open edX."},
                status=status.HTTP_409_CONFLICT,
            )
        result = client.configure_course_live(mapping.course_id, provider)
        if result.get("message"):
            return Response(
                {"error": result["message"]},
                status=status.HTTP_409_CONFLICT,
            )
        if result.get("provider_type") != "big_blue_button" or not result.get(
            "enabled"
        ):
            return Response(
                {"error": "Open edX did not activate BigBlueButton."},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        return Response(
            {
                "status": "ok",
                "course_id": mapping.course_id,
                "provider": "big_blue_button",
                "configuration": result,
            }
        )
    except Exception as exc:
        logger.exception("Failed to configure course_live for %s", mapping.course_id)
        return Response({"error": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)


@api_view(["POST"])
@permission_classes([IsAdminUser])
def sync_enroll(request):
    from apps.etudiants.models import Etudiant

    etudiant_id = request.data.get("etudiant_id")
    course_mapping_id = request.data.get("course_mapping_id")
    mode = request.data.get("mode", "audit")
    try:
        etudiant = Etudiant.objects.get(pk=etudiant_id)
        course_mapping = EdxCourseMapping.objects.get(pk=course_mapping_id)
    except (Etudiant.DoesNotExist, EdxCourseMapping.DoesNotExist):
        return Response({"error": "Not found"}, status=404)
    service = SyncService()
    try:
        enrollment = service.sync_enrollment_to_lms(etudiant, course_mapping, mode=mode)
        return Response({"status": "ok", "enrollment_id": enrollment.enrollment_id})
    except Exception as e:
        return Response({"error": str(e)}, status=500)


@api_view(["POST"])
@permission_classes([IsAdminUser])
def sync_grade(request):
    from apps.etudiants.models import Etudiant

    etudiant_id = request.data.get("etudiant_id")
    course_mapping_id = request.data.get("course_mapping_id")
    subsection_id = request.data.get("subsection_id")
    score = request.data.get("score")
    max_score = request.data.get("max_score", 20.0)
    try:
        etudiant = Etudiant.objects.get(pk=etudiant_id)
        course_mapping = EdxCourseMapping.objects.get(pk=course_mapping_id)
    except (Etudiant.DoesNotExist, EdxCourseMapping.DoesNotExist):
        return Response({"error": "Not found"}, status=404)
    service = SyncService()
    try:
        result = service.sync_grade_to_lms(
            etudiant, course_mapping, subsection_id, score, max_score
        )
        return Response({"status": "ok", "result": result})
    except Exception as e:
        return Response({"error": str(e)}, status=500)


@api_view(["POST"])
@permission_classes([IsAdminUser])
def sync_certificate(request):
    from apps.etudiants.models import Etudiant

    etudiant_id = request.data.get("etudiant_id")
    course_mapping_id = request.data.get("course_mapping_id")
    cert_type = request.data.get("certificate_type", "honor")
    try:
        etudiant = Etudiant.objects.get(pk=etudiant_id)
        course_mapping = EdxCourseMapping.objects.get(pk=course_mapping_id)
    except (Etudiant.DoesNotExist, EdxCourseMapping.DoesNotExist):
        return Response({"error": "Not found"}, status=404)
    service = SyncService()
    try:
        result = service.sync_certificate_to_lms(etudiant, course_mapping, cert_type)
        return Response({"status": "ok", "result": result})
    except Exception as e:
        return Response({"error": str(e)}, status=500)


@api_view(["GET"])
@permission_classes([IsAdminUser])
def health(request):
    checks = get_edx_client().health_check()
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
