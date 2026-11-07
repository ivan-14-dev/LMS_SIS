import hashlib
import logging
from contextlib import contextmanager

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError, connection, transaction
from django.utils.decorators import method_decorator
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey
from organizations.api import add_organization_course, ensure_organization
from rest_framework import serializers
from rest_framework.exceptions import APIException, NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from cms.djangoapps.contentstore.utils import add_instructor, initialize_permissions, update_course_discussions_settings
from cms.djangoapps.contentstore.views.course import create_new_course, default_enable_flexible_peer_openassessments
from common.djangoapps.student.auth import has_studio_write_access, is_content_creator
from xmodule.modulestore.django import modulestore
from xmodule.modulestore.exceptions import DuplicateCourseError

from .authentication import ProvisioningAuthentication
from .models import ManagedCourse

logger = logging.getLogger(__name__)
OWNERSHIP_FIELD = "sis_provisioning"


class CourseConflict(APIException):
    status_code = 409
    default_detail = "The course binding or initialization requires an explicit administrative decision."
    default_code = "course_conflict"


class CanProvisionCourses(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_active
            and request.user.has_perm("sis_provisioning.provision_courses")
        )


class CourseFields(serializers.Serializer):
    display_name = serializers.CharField(max_length=300)

    def to_internal_value(self, data):
        if not isinstance(data, dict) or set(data) != {"display_name"}:
            raise ValidationError({"non_field_errors": ["Only the course display_name is accepted."]})
        return super().to_internal_value(data)


def parse_course_key(value):
    try:
        key = CourseKey.from_string(value)
    except InvalidKeyError as error:
        raise ValidationError({"course_id": "Invalid course key."}) from error
    if len(value) > 200 or key.deprecated or key.branch or key.version_guid or str(key) != value:
        raise ValidationError({"course_id": "A canonical, unversioned course-v1 key is required."})
    if not settings.ALLOW_UNICODE_COURSE_ID and not value.isascii():
        raise ValidationError({"course_id": "Unicode course identifiers are disabled in Studio."})
    return key


def check_manager(user, key):
    if (
        not user.is_active
        or not user.has_perm("sis_provisioning.provision_courses")
        or not is_content_creator(user, key.org)
    ):
        raise PermissionDenied("This service is not authorized to provision courses in this organization.")


def check_binding(binding, user, key):
    if binding.manager_id != user.pk:
        raise PermissionDenied("This course belongs to another provisioning service.")
    if binding.revoked:
        raise CourseConflict("This course binding has been revoked.")
    if binding.course_id != str(key):
        raise CourseConflict("The course key does not match the recorded identity.")


def ownership(binding):
    return {"binding": str(binding.ownership_token), "manager": binding.manager_id}


def check_course(course, binding):
    if course.other_course_settings.get(OWNERSHIP_FIELD) != ownership(binding):
        raise CourseConflict("This course was not created under the recorded SIS binding.")


def course_payload(course):
    return {"id": str(course.id), "display_name": course.display_name}


@contextmanager
def course_lock(binding):
    if connection.vendor != "mysql":
        raise RuntimeError("Course provisioning requires the qualified MySQL advisory-lock backend.")
    identity = f"{connection.settings_dict['NAME']}:{binding.pk}"
    name = "sis_course_" + hashlib.sha256(identity.encode()).hexdigest()[:52]
    with connection.cursor() as cursor:
        cursor.execute("SELECT GET_LOCK(%s, %s)", [name, 30])
        if cursor.fetchone()[0] != 1:
            raise CourseConflict("Another provisioning operation is running; retry this request.")
    try:
        yield
    finally:
        with connection.cursor() as cursor:
            cursor.execute("SELECT RELEASE_LOCK(%s)", [name])
            if cursor.fetchone()[0] != 1:
                raise RuntimeError("The course provisioning lock was lost.")


def resume_initialization(course, user):
    # Replay only unfinished native initialization, not later authoring changes.
    add_instructor(course.id, user, user)
    initialize_permissions(course.id, user)
    add_organization_course(ensure_organization(course.id.org), course.id)
    update_course_discussions_settings(course)
    if default_enable_flexible_peer_openassessments(course.id):
        course.force_on_flexible_peer_openassessments = True
    modulestore().update_item(course, user.pk)


@method_decorator(transaction.non_atomic_requests, name="dispatch")
class CourseView(APIView):
    authentication_classes = [ProvisioningAuthentication]
    permission_classes = [CanProvisionCourses]

    def get(self, request, course_key):
        key = parse_course_key(course_key)
        manager = get_user_model().objects.get(pk=request.user.pk)
        check_manager(manager, key)
        binding = ManagedCourse.objects.filter(course_id=str(key)).first()
        if binding is None:
            raise NotFound("This course has not been bound to the SIS service.")
        check_binding(binding, manager, key)
        course = modulestore().get_course(key)
        if course is None or not binding.initialized:
            raise CourseConflict()
        check_course(course, binding)
        if not has_studio_write_access(manager, key):
            raise PermissionDenied()
        return Response(course_payload(course))

    def post(self, request, course_key):
        return self._save(request, course_key, create=True)

    def patch(self, request, course_key):
        return self._save(request, course_key, create=False)

    def _save(self, request, course_key, *, create):
        key = parse_course_key(course_key)
        fields = CourseFields(data=request.data)
        fields.is_valid(raise_exception=True)
        store = modulestore()
        try:
            # Commit the ownership intent before touching non-transactional MongoDB.
            with transaction.atomic():
                manager = get_user_model().objects.select_for_update().get(pk=request.user.pk)
                check_manager(manager, key)
                binding = ManagedCourse.objects.filter(course_id=str(key)).first()
                if binding is None:
                    if not create:
                        raise NotFound("This course has not been bound to the SIS service.")
                    if store.has_course(key, ignore_case=True):
                        raise CourseConflict("An existing course cannot be implicitly adopted.")
                    binding = ManagedCourse.objects.create(course_id=str(key), manager=manager)
                check_binding(binding, manager, key)
        except IntegrityError as error:
            logger.warning("SIS course ownership conflict service_id=%s", request.user.pk)
            raise CourseConflict() from error

        # Native creation writes a SQL course index and MongoDB content. Keep
        # autocommit so a later failure cannot orphan the MongoDB course.
        with course_lock(binding):
            manager = get_user_model().objects.get(pk=request.user.pk)
            check_manager(manager, key)
            binding = ManagedCourse.objects.get(pk=binding.pk)
            check_binding(binding, manager, key)
            if binding.adopted and not binding.initialized:
                raise CourseConflict("The operator must finish the explicit course binding.")
            course = store.get_course(key)
            created = course is None
            if course is None:
                if binding.initialized or not create:
                    raise CourseConflict("A missing managed course cannot be recreated implicitly.")
                try:
                    course = create_new_course(
                        manager,
                        key.org,
                        key.course,
                        key.run,
                        {
                            "display_name": fields.validated_data["display_name"],
                            "wiki_slug": f"{key.org}.{key.course}.{key.run}",
                            "other_course_settings": {OWNERSHIP_FIELD: ownership(binding)},
                            "catalog_visibility": "none",
                        },
                    )
                except DuplicateCourseError as error:
                    raise CourseConflict("A concurrent creation already occupies this course key.") from error
            check_course(course, binding)
            if not binding.initialized:
                if not created:
                    if not has_studio_write_access(manager, key):
                        raise PermissionDenied("The service no longer has course authoring access.")
                    resume_initialization(course, manager)
                binding.initialized = True
            elif not has_studio_write_access(manager, key):
                raise PermissionDenied("The service no longer has course authoring access.")
            name = fields.validated_data["display_name"]
            if course.display_name != name:
                course.display_name = name
                course = store.update_item(course, manager.pk)
            binding.save(update_fields=["initialized", "updated_at"])
            result = course_payload(course)
        logger.info("SIS course provisioned service_id=%s binding_id=%s created=%s", manager.pk, binding.pk, created)
        return Response(result, status=201 if created else 200)
