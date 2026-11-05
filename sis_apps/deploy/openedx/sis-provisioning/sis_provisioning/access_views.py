import logging

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey
from rest_framework import serializers
from rest_framework.exceptions import APIException, NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from common.djangoapps.student.models import CourseEnrollment
from common.djangoapps.student.roles import CourseInstructorRole, CourseStaffRole
from openedx.core.djangoapps.enrollments import api as enrollment_api
from xmodule.modulestore.django import modulestore

from .authentication import ProvisioningAuthentication
from .models import ManagedAccess, ManagedAccount, ManagedCourse

logger = logging.getLogger(__name__)


class AccessConflict(APIException):
    status_code = 409
    default_detail = "The recorded access or its current native state requires an explicit administrative decision."


class AccessFields(serializers.Serializer):
    is_active = serializers.BooleanField()
    requested_at = serializers.CharField()

    def to_internal_value(self, data):
        if not isinstance(data, dict) or set(data) != set(self.fields) or type(data.get("is_active")) is not bool:
            raise ValidationError({"non_field_errors": ["Only is_active (boolean) and requested_at are accepted."]})
        return super().to_internal_value(data)

    def validate_requested_at(self, value):
        try:
            result = parse_datetime(value)
        except ValueError as error:
            raise ValidationError("An ISO timestamp with timezone is required.") from error
        if result is None or timezone.is_naive(result):
            raise ValidationError("An ISO timestamp with timezone is required.")
        return result


def access_key(value):
    try:
        key = CourseKey.from_string(value)
    except InvalidKeyError as error:
        raise ValidationError("Invalid course key.") from error
    if len(value) > 200 or key.deprecated or key.branch or key.version_guid or str(key) != value:
        raise ValidationError("A canonical course-v1 key is required.")
    return key


class AccessView(APIView):
    authentication_classes = [ProvisioningAuthentication]
    permission_classes = [IsAuthenticated]
    kind = "enrollment"
    permission = "sis_provisioning.manage_enrollments"

    def post(self, request, course_key, username):
        fields = AccessFields(data=request.data)
        fields.is_valid(raise_exception=True)
        active = fields.validated_data["is_active"]
        requested_at = fields.validated_data["requested_at"]
        key = access_key(course_key)
        with transaction.atomic():
            manager = get_user_model().objects.select_for_update().get(pk=request.user.pk)
            if not manager.is_active or not manager.has_perm(self.permission):
                raise PermissionDenied()
            course = ManagedCourse.objects.select_for_update().filter(course_id=str(key)).first()
            account = ManagedAccount.objects.select_for_update().filter(username=username).first()
            if course is None or account is None:
                raise NotFound("An explicit course and account binding is required.")
            if course.manager_id != manager.pk or account.manager_id != manager.pk:
                raise PermissionDenied("The service must own both the account and the course.")
            user = get_user_model().objects.select_for_update().get(pk=account.user_id)
            if user.username != username or user.pk == manager.pk or user.is_staff or user.is_superuser:
                raise AccessConflict()
            native_course = modulestore().get_course(key)
            marker = {"binding": str(course.ownership_token), "manager": manager.pk}
            if native_course is not None and native_course.other_course_settings.get("sis_provisioning") != marker:
                raise AccessConflict("The native course ownership no longer matches.")
            if active:
                if course.revoked or not course.initialized or not user.is_active:
                    raise AccessConflict("Revoked or unfinished bindings cannot grant access.")
                if not CourseInstructorRole(key).has_user(manager):
                    raise PermissionDenied("Course instructor access is required to grant access.")
                if native_course is None:
                    raise AccessConflict("The native course ownership no longer matches.")
            access = (
                ManagedAccess.objects.select_for_update().filter(course=course, account=account, kind=self.kind).first()
            )
            if access:
                if requested_at < access.requested_at:
                    raise AccessConflict({"code": "stale_request", "detail": "A newer access decision is recorded."})
                if requested_at == access.requested_at and active != access.is_active:
                    raise AccessConflict("The same request timestamp must not change its intent.")
            else:
                access = ManagedAccess(course=course, account=account, kind=self.kind, requested_at=requested_at)
            if self.kind == "enrollment":
                native_id = self.set_enrollment(user, key, access, active, requested_at)
            else:
                native_id = self.set_teaching(user, key, access, active, requested_at)
            access.is_active = active
            access.requested_at = requested_at
            access.initialized = True
            access.save()
        logger.info(
            "SIS access applied manager_id=%s binding_id=%s kind=%s active=%s", manager.pk, access.pk, self.kind, active
        )
        return Response(
            {
                "id": native_id,
                "course_id": str(key),
                "username": username,
                "kind": self.kind,
                "is_active": active,
                "requested_at": requested_at.isoformat(),
            }
        )

    @staticmethod
    def set_enrollment(user, key, access, active, requested_at):
        current = CourseEnrollment.objects.select_for_update().filter(user=user, course_id=key).first()
        if not access.initialized and current:
            raise AccessConflict("An existing enrollment is not implicitly adopted.")
        if current and current.mode != "audit":
            raise AccessConflict("Only audit enrollments are managed; paid and other modes are preserved.")
        if access.initialized and requested_at == access.requested_at:
            if bool(current and current.is_active) != active:
                raise AccessConflict("Native access changed after this request; an explicit new decision is required.")
        elif active:
            if not current or not current.is_active:
                enrollment_api.add_enrollment(user.username, str(key), mode="audit")
        elif current and current.is_active:
            enrollment_api.update_enrollment(user.username, str(key), is_active=False)
        confirmed = CourseEnrollment.objects.filter(user=user, course_id=key).first()
        if bool(confirmed and confirmed.is_active) != active:
            raise AccessConflict("The native enrollment did not confirm the requested state.")
        return confirmed.pk if confirmed else None

    @staticmethod
    def set_teaching(user, key, access, active, requested_at):
        role = CourseStaffRole(key)
        current = role.has_user(user, check_user_activation=False)
        if not access.initialized and current:
            raise AccessConflict("An existing course staff role is not implicitly adopted.")
        if access.initialized and requested_at == access.requested_at:
            if current != active:
                raise AccessConflict("Native authoring rights changed after this request.")
        elif active and not current:
            role.add_users(user)
        elif not active and current:
            role.remove_users(user)
        confirmed = role.has_user(get_user_model().objects.get(pk=user.pk), check_user_activation=False)
        if confirmed != active:
            raise AccessConflict("The native course role did not confirm the requested state.")
        return None


class TeachingView(AccessView):
    kind = "teaching"
    permission = "sis_provisioning.manage_teaching"
