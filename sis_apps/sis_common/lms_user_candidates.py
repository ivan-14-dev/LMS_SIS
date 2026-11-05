"""Read-only candidates for a first, explicitly confirmed LMS association."""

from django.contrib.auth import get_user_model
from django.db.models import Q
from guardian.conf import settings as guardian_settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAdminUser

from sis_common.lms_identity import lms_username
from sis_common.lms_tenants import current_lms_tenant


@api_view(["GET"])
@permission_classes([IsAdminUser])
def user_candidates(request):
    from apps.integration.models import EdxUserMapping

    tenant = current_lms_tenant(request)
    if set(request.query_params) - {"page"} or len(request.query_params.getlist("page")) > 1:
        raise ValidationError({"error": "Seul le paramètre de pagination page est accepté."})
    users = (
        get_user_model().objects.filter(is_active=True)
        .exclude(username=guardian_settings.ANONYMOUS_USER_NAME)
        .filter(Q(etablissement_id=tenant.pk) | Q(etablissement_id__isnull=True))
        .exclude(pk__in=EdxUserMapping.objects.values("user_sis_id"))
        .only("pk", "username", "first_name", "last_name", "integration_id")
        .order_by("pk")
    )
    paginator = PageNumberPagination()
    page = paginator.paginate_queryset(users, request)
    return paginator.get_paginated_response([
        {
            "user_sis": user.pk,
            "user_sis_username": user.username,
            "user_sis_name": user.get_full_name() or user.username,
            "username_edx": lms_username(user),
            "user_id_edx": None,
            "actif": True,
        }
        for user in page
    ])
