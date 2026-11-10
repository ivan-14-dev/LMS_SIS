"""Personal navigation based on confirmed, current SIS-owned LMS access."""

from django.apps import apps
from django.conf import settings
from django.db.models import F, Q
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .lms_access_sync import revocation_reason
from .lms_tenants import current_lms_tenant


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def learning_access(request):
    from apps.integration.models import EdxAccessIntent, EdxUserMapping
    from apps.portail.api import portal_capabilities

    tenant = current_lms_tenant(request)
    portals = portal_capabilities(request)["portals"]
    teaching = request.user.role == "enseignant" and portals["staff"]
    if not (portals["learner"] or teaching):
        raise PermissionDenied("Cet accès est réservé aux apprenants et enseignants affiliés.")
    if not settings.EDX_LMS_URL:
        return Response({"state": "not_configured", "courses": [], "can_open_studio": False})
    mapping = EdxUserMapping.objects.filter(
        user_sis=request.user, actif=True, user_id_edx__gt=0, date_sync__isnull=False
    ).first()
    if mapping is None:
        return Response({"state": "unmapped", "courses": [], "can_open_studio": False})
    kind = "teaching" if teaching else "enrollment"
    intents = EdxAccessIntent.objects.filter(
        user=request.user,
        mapping=mapping,
        kind=kind,
        is_active=True,
        course__actif=True,
        applied_requested_at=F("requested_at"),
    )
    if apps.is_installed("apps.classes"):
        intents = intents.filter(
            Q(course__matiere__etablissement_id=tenant.pk) | Q(course__matiere__etablissement__isnull=True),
            Q(course__classe__etablissement_id=tenant.pk) | Q(course__classe__etablissement__isnull=True),
            course__classe__annee_scolaire__etablissement_id=tenant.pk,
            course__classe__niveau__etablissement_id=tenant.pk,
        ).select_related("course__classe")
    else:
        intents = intents.filter(
            Q(course__ecue__ue__maquette__formation__departement__isnull=True)
            | Q(course__ecue__ue__maquette__formation__departement__faculte__universite_id=tenant.pk),
            course__ecue__ue__semestre__annee_universitaire__universite_id=tenant.pk,
            course__ecue__ue__maquette__annee_universitaire__universite_id=tenant.pk,
        ).select_related("course__ecue__ue__semestre", "course__ecue__ue__maquette")
    courses = [
        {
            "course_id": intent.course.course_id,
            "name": intent.course.course_name,
            "can_edit": teaching and bool(settings.EDX_CMS_URL),
        }
        for intent in intents.order_by("course__course_name", "pk")
        if revocation_reason(request.user, intent.course, mapping, kind) is None
    ]
    response = Response(
        {"state": "ready", "courses": courses, "can_open_studio": any(course["can_edit"] for course in courses)}
    )
    response["Cache-Control"] = "private, no-store"
    return response
