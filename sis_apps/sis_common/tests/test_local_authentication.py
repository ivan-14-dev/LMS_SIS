"""Local JWT tenant isolation without a database or external services."""

from types import SimpleNamespace
from unittest.mock import patch

import pyotp
import pytest
from apps.utilisateurs.token_views import MFATokenObtainPairSerializer
from django.conf import settings
from django.test import RequestFactory, override_settings
from rest_framework.exceptions import AuthenticationFailed, ValidationError
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from sis_common.local_authentication import (
    TENANT_CLAIM,
    TenantJWTAuthentication,
    TenantRefreshToken,
    TenantTokenBlacklistSerializer,
    TenantTokenRefreshSerializer,
)


@pytest.fixture
def tenant_connection():
    tenant = SimpleNamespace(pk=11, schema_name="school_a")
    connection = SimpleNamespace(tenant=tenant, schema_name=tenant.schema_name)
    with patch("sis_common.local_authentication.connection", connection):
        yield connection


def local_request(token, prefix="Bearer"):
    return RequestFactory().get("/api/v1/utilisateurs/comptes/me/", HTTP_AUTHORIZATION=f"{prefix} {token}")


def test_issued_pair_and_outstanding_record_include_tenant_identity(tenant_connection):
    user = SimpleNamespace(id=42, is_active=True)
    with patch("rest_framework_simplejwt.tokens.OutstandingToken.objects.create") as create:
        refresh = TenantRefreshToken.for_user(user)
    expected = f"{settings.TENANT_MODEL}:{tenant_connection.tenant.pk}"
    assert refresh[TENANT_CLAIM] == refresh.access_token[TENANT_CLAIM] == expected
    stored = RefreshToken(create.call_args.kwargs["token"], verify=False)
    assert stored[TENANT_CLAIM] == expected


@pytest.mark.parametrize(
    ("mfa_active", "mfa_code", "succeeds"),
    [(False, "", True), (True, "", False), (True, "invalid", False), (True, "valid", True)],
)
def test_local_issuer_preserves_mfa_requirement(tenant_connection, mfa_active, mfa_code, succeeds):
    user = SimpleNamespace(id=42, is_active=True, mfa_active=mfa_active, mfa_secret=pyotp.random_base32())
    attrs = {"username": "local-test", "password": "test-only"}
    if mfa_code:
        attrs["mfa_code"] = pyotp.TOTP(user.mfa_secret).now() if mfa_code == "valid" else mfa_code
    with (
        patch("rest_framework_simplejwt.serializers.authenticate", return_value=user),
        patch("rest_framework_simplejwt.serializers.update_last_login"),
        patch("rest_framework_simplejwt.tokens.OutstandingToken.objects.create"),
    ):
        if not succeeds:
            with pytest.raises(ValidationError):
                MFATokenObtainPairSerializer().validate(attrs)
        else:
            pair = MFATokenObtainPairSerializer().validate(attrs)
            expected = f"{settings.TENANT_MODEL}:{tenant_connection.tenant.pk}"
            assert RefreshToken(pair["refresh"], verify=False)[TENANT_CLAIM] == expected
            assert AccessToken(pair["access"])[TENANT_CLAIM] == expected


def test_matching_access_resolves_user_and_preserves_federated_header_separation(tenant_connection):
    access = TenantRefreshToken().access_token
    access["user_id"] = "42"
    user = SimpleNamespace(pk=42)
    authenticator = TenantJWTAuthentication()
    with patch.object(JWTAuthentication, "get_user", return_value=user) as get_user:
        actual_user, validated = authenticator.authenticate(local_request(access))
        assert actual_user is user
        get_user.assert_called_once_with(validated)
        assert authenticator.authenticate(local_request(access, "JWT")) is None


@pytest.mark.parametrize("claim", [None, "", 11, True, [], {}, "etablissement.Foreign:11", "wrong-tenant"])
def test_access_rejects_missing_or_wrong_tenant_before_user_lookup(tenant_connection, claim):
    access = AccessToken()
    access["user_id"] = "42"
    if claim is not None:
        access[TENANT_CLAIM] = claim
    with patch.object(JWTAuthentication, "get_user") as get_user:
        with pytest.raises(AuthenticationFailed):
            TenantJWTAuthentication().authenticate(local_request(access))
        get_user.assert_not_called()


def test_same_numeric_user_id_cannot_cross_schema_identities(tenant_connection):
    access = TenantRefreshToken().access_token
    access["user_id"] = "42"
    tenant_connection.tenant = SimpleNamespace(pk=12, schema_name="school_b")
    tenant_connection.schema_name = "school_b"
    staff_with_same_id = SimpleNamespace(pk=42, is_staff=True)
    with patch.object(JWTAuthentication, "get_user", return_value=staff_with_same_id) as get_user:
        with pytest.raises(AuthenticationFailed):
            TenantJWTAuthentication().authenticate(local_request(access))
        get_user.assert_not_called()


@pytest.mark.parametrize("serializer_class", [TenantTokenRefreshSerializer, TenantTokenBlacklistSerializer])
@pytest.mark.parametrize("claim", [None, "other-tenant"])
def test_refresh_and_logout_reject_tenant_before_any_local_query(tenant_connection, serializer_class, claim):
    refresh = RefreshToken()
    refresh["user_id"] = "42"
    if claim is not None:
        refresh[TENANT_CLAIM] = claim
    with (
        patch.object(RefreshToken, "check_blacklist") as check_blacklist,
        patch("rest_framework_simplejwt.serializers.get_user_model") as get_user_model,
        patch("rest_framework_simplejwt.tokens.get_user_model") as token_user_model,
    ):
        with pytest.raises(AuthenticationFailed):
            serializer_class().validate({"refresh": str(refresh)})
        check_blacklist.assert_not_called()
        get_user_model.assert_not_called()
        token_user_model.assert_not_called()


def test_refresh_rotation_preserves_binding_and_revocation(tenant_connection):
    refresh = TenantRefreshToken()
    refresh["user_id"] = "42"
    with (
        patch.object(api_settings, "ROTATE_REFRESH_TOKENS", True),
        patch.object(api_settings, "BLACKLIST_AFTER_ROTATION", True),
        patch.object(RefreshToken, "check_blacklist") as check_blacklist,
        patch.object(RefreshToken, "blacklist") as blacklist,
        patch.object(RefreshToken, "outstand") as outstand,
        patch("rest_framework_simplejwt.serializers.get_user_model") as get_user_model,
    ):
        get_user_model.return_value.objects.get.return_value = SimpleNamespace(is_active=True)
        result = TenantTokenRefreshSerializer().validate({"refresh": str(refresh)})
        check_blacklist.assert_called_once()
        blacklist.assert_called_once()
        outstand.assert_called_once()
        get_user_model.return_value.objects.get.assert_called_once_with(id="42")
    rotated = RefreshToken(result["refresh"], verify=False)
    assert rotated[TENANT_CLAIM] == AccessToken(result["access"])[TENANT_CLAIM] == refresh[TENANT_CLAIM]
    assert rotated["jti"] != refresh["jti"]


def test_bound_refresh_still_rejects_blacklisted_tokens(tenant_connection):
    refresh = TenantRefreshToken()
    with patch.object(RefreshToken, "check_blacklist", side_effect=TokenError("Token is blacklisted")):
        with pytest.raises(TokenError, match="blacklisted"):
            TenantTokenRefreshSerializer().validate({"refresh": str(refresh)})


@pytest.mark.parametrize("state", ["absent", "unsaved", "public", "schema-mismatch"])
def test_missing_or_inconsistent_tenant_context_fails_closed(tenant_connection, state):
    refresh = TenantRefreshToken()
    if state == "absent":
        tenant_connection.tenant = None
    elif state == "unsaved":
        tenant_connection.tenant.pk = None
    elif state == "public":
        tenant_connection.tenant.schema_name = tenant_connection.schema_name = "public"
    else:
        tenant_connection.schema_name = "school_b"
    with pytest.raises(AuthenticationFailed):
        TenantRefreshToken()
    with pytest.raises(AuthenticationFailed):
        TenantJWTAuthentication().get_user(refresh.access_token)
    with pytest.raises(AuthenticationFailed):
        TenantTokenRefreshSerializer().validate({"refresh": str(refresh)})


def test_tenant_model_namespace_cannot_be_reused_in_other_variant(tenant_connection):
    access = TenantRefreshToken().access_token
    with override_settings(TENANT_MODEL="etablissement.OtherVariant"):
        with pytest.raises(AuthenticationFailed):
            TenantJWTAuthentication().get_user(access)
