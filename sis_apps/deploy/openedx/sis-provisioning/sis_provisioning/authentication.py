from django.contrib.auth import get_user_model
from edx_rest_framework_extensions.auth.jwt.authentication import JwtAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import BasePermission


class ProvisioningAuthentication(JwtAuthentication):
    def authenticate(self, request):
        header = request.META.get("HTTP_AUTHORIZATION", "")
        if not header:
            return None
        if len(header.split()) != 2 or header.split()[0].lower() != "jwt":
            raise AuthenticationFailed("An explicit JWT authorization header is required.")
        return super().authenticate(request)

    def authenticate_credentials(self, payload):
        if payload.get("is_restricted") is not False:
            raise AuthenticationFailed("An unrestricted service token is required.")
        username = self._get_username_from_payload(payload)
        try:
            user = get_user_model().objects.get(username=username, is_active=True)
        except get_user_model().DoesNotExist as error:
            raise AuthenticationFailed("The service account is unavailable.") from error
        return user


class CanProvisionAccounts(BasePermission):
    message = "This account is not authorized to provision SIS users."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_active
            and request.user.has_perm("sis_provisioning.provision_accounts")
        )
