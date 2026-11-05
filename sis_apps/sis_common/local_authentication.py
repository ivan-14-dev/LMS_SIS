"""Tenant-bound local JWTs, separate from the federated Open edX authenticator.

Pre-existing JWTs without the tenant claim are intentionally rejected, including
refresh tokens: local users must sign in again after this change is deployed.
"""

from django.conf import settings
from django.db import connection
from django_tenants.utils import get_public_schema_name
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.serializers import TokenBlacklistSerializer, TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken

TENANT_CLAIM = "sis_tenant_id"


def current_tenant_identity():
    tenant = getattr(connection, "tenant", None)
    tenant_id = getattr(tenant, "pk", None)
    schema = getattr(tenant, "schema_name", None)
    if (
        tenant_id is None
        or not schema
        or schema == get_public_schema_name()
        or schema != getattr(connection, "schema_name", None)
    ):
        raise AuthenticationFailed("Établissement d'authentification local invalide.")
    # Registry PKs are stable across domain changes; qualify the two SIS models.
    return f"{settings.TENANT_MODEL}:{tenant_id}"


def validate_token_tenant(token):
    if token.get(TENANT_CLAIM) != current_tenant_identity():
        raise AuthenticationFailed("Ce jeton local ne correspond pas à cet établissement.")


class TenantJWTAuthentication(JWTAuthentication):
    def get_user(self, validated_token):
        validate_token_tenant(validated_token)
        return super().get_user(validated_token)


class TenantRefreshToken(RefreshToken):
    def __init__(self, token=None, verify=True):
        super().__init__(token, verify)
        if token is None:
            self[TENANT_CLAIM] = current_tenant_identity()

    def verify(self):
        # Signature validation precedes this hook; no tenant-local DB lookup may
        # happen before the tenant check, including the refresh blacklist query.
        validate_token_tenant(self)
        super().verify()


class TenantTokenRefreshSerializer(TokenRefreshSerializer):
    token_class = TenantRefreshToken


class TenantTokenBlacklistSerializer(TokenBlacklistSerializer):
    token_class = TenantRefreshToken
