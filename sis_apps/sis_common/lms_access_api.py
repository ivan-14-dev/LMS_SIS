"""Administrative access decisions shared by the two SIS variants."""

import logging

import requests
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from .authorization import has_business_permission
from .lms_access_sync import dispatch_access, learner_model

logger = logging.getLogger(__name__)


class AccessRequestSerializer(serializers.Serializer):
    course_mapping_id = serializers.IntegerField(min_value=1)
    active = serializers.BooleanField(default=True)

    def __init__(self, *, identity_field, enrollment, **kwargs):
        super().__init__(**kwargs)
        self.fields[identity_field] = serializers.IntegerField(min_value=1)
        if enrollment:
            self.fields["mode"] = serializers.ChoiceField(choices=["audit"], default="audit")

    def to_internal_value(self, data):
        if not isinstance(data, dict) or set(data) - set(self.fields):
            raise serializers.ValidationError({"non_field_errors": ["La demande contient des champs inconnus."]})
        if "active" in data and type(data["active"]) is not bool:
            raise serializers.ValidationError({"active": "Un booléen est requis."})
        return super().to_internal_value(data)


def synchronize_access(request, *, kind):
    from apps.integration.models import EdxCourseMapping, EdxEnrollment, EdxUserMapping
    from apps.integration.sync_service import SyncService

    permission = "integration.change_edxaccessintent"
    if not request.user.is_superuser and not request.user.has_perm(permission):
        raise PermissionDenied("Vous ne pouvez pas administrer les accès LMS.")
    model, learner_field = learner_model()
    identity_field = f"{learner_field}_id" if kind == "enrollment" else "user_id"
    serializer = AccessRequestSerializer(
        data=request.data,
        identity_field=identity_field,
        enrollment=kind == "enrollment",
    )
    serializer.is_valid(raise_exception=True)
    values = serializer.validated_data
    if not has_business_permission(
        request.user, permission, context={"courses": values["course_mapping_id"], "kinds": kind}
    ):
        raise PermissionDenied("Vous ne pouvez pas administrer les accès à ce cours LMS.")
    course = get_object_or_404(EdxCourseMapping, pk=values["course_mapping_id"])
    learner = None
    if kind == "enrollment":
        learner = get_object_or_404(model.objects.select_related("user"), pk=values[identity_field])
        user = learner.user
    else:
        user = get_object_or_404(get_user_model(), pk=values[identity_field])
    try:
        intent = dispatch_access(SyncService(), user, course, kind=kind, active=values["active"])
    except EdxUserMapping.DoesNotExist:
        logger.warning("LMS access refused: missing account mapping user_id=%s course_id=%s", user.pk, course.pk)
        return Response(
            {"error": "Synchronisez le compte utilisateur avant de modifier ses accès LMS."},
            status=status.HTTP_409_CONFLICT,
        )
    except ValueError as error:
        logger.warning("LMS access decision rejected user_id=%s course_id=%s: %s", user.pk, course.pk, error)
        return Response({"error": str(error)}, status=status.HTTP_409_CONFLICT)
    except requests.RequestException:
        logger.exception("LMS access not confirmed user_id=%s course_id=%s", user.pk, course.pk)
        return Response(
            {"error": "Le LMS n'a pas confirmé l'accès. Consultez la demande dans la file de synchronisation."},
            status=status.HTTP_502_BAD_GATEWAY,
        )
    intent.refresh_from_db()
    if intent.applied_requested_at != intent.requested_at:
        return Response(
            {"error": "Une décision plus récente est en attente de confirmation.", "intent_id": intent.pk},
            status=status.HTTP_409_CONFLICT,
        )
    result = {
        "status": "ok",
        "intent_id": intent.pk,
        "kind": intent.kind,
        "is_active": intent.is_active,
        "requested_at": intent.requested_at.isoformat(),
    }
    if learner is not None:
        enrollment = EdxEnrollment.objects.filter(**{learner_field: learner}, course=course).first()
        result["enrollment_id"] = enrollment.enrollment_id if enrollment else None
    logger.info(
        "LMS access confirmed actor_id=%s user_id=%s course_id=%s kind=%s active=%s intent_id=%s",
        request.user.pk,
        user.pk,
        course.pk,
        kind,
        intent.is_active,
        intent.pk,
    )
    return Response(result)
