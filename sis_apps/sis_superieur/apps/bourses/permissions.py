"""Permissions for bourses."""

from rest_framework.permissions import IsAuthenticated

from sis_common.authorization import is_current_tenant_user, request_has_business_access


class CanAwardBourse(IsAuthenticated):
    def has_permission(self, request, view):
        if not super().has_permission(request, view) or not is_current_tenant_user(request):
            return False
        permission = {
            "create": "bourses.add_attributionbourse",
            "creer_attribution": "bourses.add_attributionbourse",
            "destroy": "bourses.delete_attributionbourse",
        }.get(view.action, "bourses.change_attributionbourse")
        return request_has_business_access(
            request,
            permission,
            ("service_social", "super_admin"),
        )
