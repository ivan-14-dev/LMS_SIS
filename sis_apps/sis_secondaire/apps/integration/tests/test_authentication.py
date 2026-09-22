"""Tests for Open edX JWT authentication."""

import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from django.test import RequestFactory, override_settings
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied

from sis_common.authentication import EdxJWTAuthentication


class TestEdxJWTAuthentication:
    """Validate tokens before resolving an existing SIS mapping."""

    @classmethod
    def setup_class(cls):
        cls.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public_jwk = json.loads(
            jwt.algorithms.RSAAlgorithm.to_jwk(cls.private_key.public_key())
        )
        public_jwk["kid"] = "test-key"
        cls.jwk_set = json.dumps({"keys": [public_jwk]})

    def setup_method(self):
        self.authenticator = EdxJWTAuthentication()
        self.request_factory = RequestFactory()
        self.user = SimpleNamespace(is_active=True)

    def _token(self, **overrides):
        now = datetime.now(tz=UTC)
        payload = {
            "aud": "sis-test-audience",
            "exp": now + timedelta(minutes=5),
            "iat": now,
            "iss": "https://lms.example.com/oauth2",
            "preferred_username": "mapped-user",
            "sub": "opaque-open-edx-user-id",
            "user_id": 42,
        }
        payload.update(overrides)
        return jwt.encode(
            payload,
            self.private_key,
            algorithm="RS512",
            headers={"kid": "test-key"},
        )

    def _request(self, token, prefix="JWT"):
        return self.request_factory.get(
            "/api/v1/integration/sync/status/",
            HTTP_AUTHORIZATION=f"{prefix} {token}",
        )

    def _authenticate(self, token, request=None):
        with override_settings(
            EDX_JWT_ALGORITHM="RS512",
            EDX_JWT_AUDIENCE="sis-test-audience",
            EDX_JWT_COOKIE_HEADER_PAYLOAD="edx-jwt-cookie-header-payload",
            EDX_JWT_COOKIE_SIGNATURE="edx-jwt-cookie-signature",
            EDX_JWT_ISSUER="https://lms.example.com/oauth2",
            EDX_JWT_LEEWAY=0,
            EDX_JWT_PUBLIC_SIGNING_JWK_SET=self.jwk_set,
        ), patch.object(self.authenticator, "_get_user", return_value=self.user):
            return self.authenticator.authenticate(request or self._request(token))

    def _cookie_request(self, token):
        header_payload, signature = token.rsplit(".", 1)
        return self.request_factory.get(
            "/api/v1/integration/sync/status/",
            HTTP_COOKIE=(
                f"edx-jwt-cookie-header-payload={header_payload}; "
                f"edx-jwt-cookie-signature={signature}"
            ),
            HTTP_USE_JWT_COOKIE="true",
        )

    def _cookie_post_request(self, token):
        header_payload, signature = token.rsplit(".", 1)
        request = self.request_factory.post(
            "/api/v1/integration/sync/user/42/",
            HTTP_COOKIE=(
                f"edx-jwt-cookie-header-payload={header_payload}; "
                f"edx-jwt-cookie-signature={signature}"
            ),
            HTTP_USE_JWT_COOKIE="true",
        )
        request._dont_enforce_csrf_checks = False
        return request

    def test_valid_token_authenticates_mapped_user(self):
        user, claims = self._authenticate(self._token())

        assert user is self.user
        assert claims["preferred_username"] == "mapped-user"

    def test_non_edx_authorization_header_is_ignored(self):
        assert (
            self.authenticator.authenticate(self._request("local-token", "Bearer"))
            is None
        )

    def test_split_open_edx_cookies_are_authenticated(self):
        token = self._token()

        user, claims = self._authenticate(token, self._cookie_request(token))

        assert user is self.user
        assert claims["preferred_username"] == "mapped-user"

    def test_split_cookies_require_explicit_mfe_header(self):
        request = self._cookie_request(self._token())
        request.META.pop("HTTP_USE_JWT_COOKIE")

        assert self.authenticator.authenticate(request) is None

    def test_split_cookie_write_requires_csrf_token(self):
        token = self._token()

        with pytest.raises(PermissionDenied):
            self._authenticate(token, self._cookie_post_request(token))

    def test_expired_token_is_rejected(self):
        with pytest.raises(AuthenticationFailed):
            self._authenticate(
                self._token(exp=datetime.now(tz=UTC) - timedelta(seconds=1))
            )

    def test_wrong_issuer_is_rejected(self):
        with pytest.raises(AuthenticationFailed):
            self._authenticate(self._token(iss="https://attacker.example.com/oauth2"))

    def test_wrong_audience_is_rejected(self):
        with pytest.raises(AuthenticationFailed):
            self._authenticate(self._token(aud="another-service"))

    def test_mapping_must_match_open_edx_identity(self):
        mapping = SimpleNamespace(
            user_id_edx=999,
            user_sis=self.user,
        )
        mapping_model = MagicMock()
        mapping_model.objects.select_related.return_value.get.return_value = mapping

        with patch(
            "sis_common.authentication.apps.get_model", return_value=mapping_model
        ), pytest.raises(AuthenticationFailed):
            self.authenticator._get_user(
                {"preferred_username": "mapped-user", "user_id": 42}
            )

        mapping_model.objects.select_related.return_value.get.assert_called_once_with(
            username_edx="mapped-user",
            actif=True,
        )
