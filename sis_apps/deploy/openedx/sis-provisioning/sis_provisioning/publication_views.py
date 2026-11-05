import logging
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils.decorators import method_decorator
from rest_framework import serializers
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from cms.djangoapps.contentstore.xblock_storage_handlers.view_handlers import _check_xblock_permission
from xmodule.modulestore import ModuleStoreEnum
from xmodule.modulestore.exceptions import VersionConflictError

from .authentication import ProvisioningAuthentication
from .course_views import CourseConflict, check_binding, check_course, course_lock, modulestore, parse_course_key
from .models import ManagedCourse, ManagedPublication

logger = logging.getLogger(__name__)


class PublicationFields(serializers.Serializer):
    operation_id = serializers.UUIDField()
    expected_revision = serializers.RegexField(r"^[a-f0-9]{24}$")
    confirm = serializers.BooleanField()

    def to_internal_value(self, data):
        if not isinstance(data, dict) or set(data) != set(self.fields) or data.get("confirm") is not True:
            raise ValidationError({"non_field_errors": ["Confirm the exact reviewed revision before publication."]})
        return super().to_internal_value(data)


def publication_context(manager_id, key, *, publish=False):
    manager = get_user_model().objects.get(pk=manager_id)
    if not manager.is_active or not manager.has_perm("sis_provisioning.publish_courses"):
        raise PermissionDenied()
    binding = ManagedCourse.objects.filter(course_id=str(key)).first()
    if binding is None:
        raise NotFound()
    check_binding(binding, manager, key)
    course = modulestore().get_course(key)
    if course is None or not binding.initialized:
        raise CourseConflict()
    check_course(course, binding)
    _check_xblock_permission(
        SimpleNamespace(user=manager, method="POST" if publish else "GET", json={"publish": "make_public"}),
        course.location,
    )
    return manager, binding, course


@method_decorator(transaction.non_atomic_requests, name="dispatch")
class PublicationView(APIView):
    authentication_classes = [ProvisioningAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, course_key):
        key = parse_course_key(course_key)
        store = modulestore()
        with store.branch_setting(ModuleStoreEnum.Branch.draft_preferred, key):
            _, _, course = publication_context(request.user.pk, key)
            return Response({"id": str(key), "revision": str(course.course_version)})

    def post(self, request, course_key):
        fields = PublicationFields(data=request.data)
        fields.is_valid(raise_exception=True)
        values = fields.validated_data
        key = parse_course_key(course_key)
        store = modulestore()
        with store.branch_setting(ModuleStoreEnum.Branch.draft_preferred, key):
            _, binding, _ = publication_context(request.user.pk, key, publish=True)
            with course_lock(binding):
                manager, binding, course = publication_context(request.user.pk, key, publish=True)
                publication, _ = ManagedPublication.objects.get_or_create(
                    operation_id=values["operation_id"],
                    defaults={"course": binding, "revision": values["expected_revision"]},
                )
                if publication.course_id != binding.pk or publication.revision != values["expected_revision"]:
                    raise CourseConflict("An operation identifier must not change course or revision.")
                if not publication.published_version:
                    if str(course.course_version) != publication.revision:
                        raise CourseConflict("The draft changed; review its new revision before publishing.")
                    if not list(store.get_items(key, qualifiers={"category": "vertical"})):
                        raise ValidationError("Create at least one unit in Studio before publication.")
                    location = course.location.replace(
                        course_key=key.replace(branch="draft", version_guid=publication.revision)
                    )
                    try:
                        published = store.publish(location, manager.pk)
                    except VersionConflictError as error:
                        raise CourseConflict("The draft changed during publication; review it again.") from error
                    publication.published_version = str(published.course_version)
                    publication.save(update_fields=["published_version"])
                logger.info("SIS publication confirmed binding_id=%s operation_id=%s", binding.pk, publication.pk)
                return Response(
                    {
                        "id": str(key),
                        "operation_id": str(publication.pk),
                        "revision": publication.revision,
                        "published_version": publication.published_version,
                    }
                )
