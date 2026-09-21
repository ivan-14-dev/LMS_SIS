"""Authentication shared by the SIS services."""

import json

import jwt
from django.apps import apps
from django.conf import settings
from rest_framework.authentication import (
    BaseAuthentication,
    SessionAuthentication,
    get_authorization_header,
)
from rest_framework.exceptions import AuthenticationFailed


class EdxJWTAuthentication(BaseAuthentication):
    """Authenticate a pre-mapped SIS user from an Open edX JWT."""

    keyword = "JWT"

    def authenticate(self, request):
        header = get_authorization_header(request).split()
        uses_cookie = False
        if not header:
            token = self._get_cookie_token(request)
            if token is None:
                return None
            uses_cookie = True
        elif header[0].decode("ascii", errors="ignore").lower() == self.keyword.lower():
            if len(header) != 2:
                raise AuthenticationFailed("En-tête d'authentification JWT invalide.")
            try:
                token = header[1].decode("ascii")
            except UnicodeDecodeError:
                raise AuthenticationFailed("Jeton JWT Open edX invalide.") from None
        else:
            return None

        try:
            unverified_header = jwt.get_unverified_header(token)
            if unverified_header.get("alg") != settings.EDX_JWT_ALGORITHM:
                raise AuthenticationFailed("Algorithme JWT Open edX invalide.")
            signing_key = self._get_signing_key(unverified_header.get("kid"))
            payload = jwt.decode(
                token,
                signing_key,
                algorithms=[settings.EDX_JWT_ALGORITHM],
                audience=settings.EDX_JWT_AUDIENCE,
                issuer=settings.EDX_JWT_ISSUER,
                leeway=settings.EDX_JWT_LEEWAY,
                options={
                    "require": [
                        "aud",
                        "exp",
                        "iat",
                        "iss",
                        "preferred_username",
                        "sub",
                    ]
                },
            )
        except AuthenticationFailed:
            raise
        except (UnicodeDecodeError, ValueError, jwt.PyJWTError):
            raise AuthenticationFailed("Jeton JWT Open edX invalide.") from None

        user = self._get_user(payload)
        if uses_cookie:
            SessionAuthentication().enforce_csrf(request)
        return user, payload

    def authenticate_header(self, request):
        return self.keyword

    @staticmethod
    def _get_cookie_token(request):
        if request.META.get("HTTP_USE_JWT_COOKIE", "").lower() != "true":
            return None
        header_payload = request.COOKIES.get(settings.EDX_JWT_COOKIE_HEADER_PAYLOAD)
        signature = request.COOKIES.get(settings.EDX_JWT_COOKIE_SIGNATURE)
        if not header_payload or not signature:
            raise AuthenticationFailed("Cookies JWT Open edX incomplets.")
        return f"{header_payload}.{signature}"

    @staticmethod
    def _get_signing_key(key_id):
        try:
            jwk_set = jwt.PyJWKSet.from_json(settings.EDX_JWT_PUBLIC_SIGNING_JWK_SET)
        except (json.JSONDecodeError, jwt.PyJWTError, ValueError, TypeError):
            raise AuthenticationFailed("Configuration JWT Open edX invalide.") from None

        matching_keys = [key for key in jwk_set.keys if key.key_id == key_id]
        if key_id is None and len(jwk_set.keys) == 1:
            matching_keys = jwk_set.keys
        if len(matching_keys) != 1:
            raise AuthenticationFailed("Clé de signature JWT Open edX inconnue.")
        return matching_keys[0].key

    @staticmethod
    def _get_user(payload):
        mapping_model = apps.get_model("integration", "EdxUserMapping")
        username = payload["preferred_username"]
        try:
            mapping = mapping_model.objects.select_related("user_sis").get(
                username_edx=username,
                actif=True,
            )
        except mapping_model.DoesNotExist:
            raise AuthenticationFailed("Aucun compte SIS actif n'est associé à cet utilisateur.") from None

        edx_user_id = payload.get("user_id")
        if (
            edx_user_id is not None
            and mapping.user_id_edx is not None
            and str(edx_user_id) != str(mapping.user_id_edx)
        ):
            raise AuthenticationFailed("Le compte Open edX ne correspond pas au mapping SIS.")
        if not mapping.user_sis.is_active:
            raise AuthenticationFailed("Ce compte SIS est désactivé.")
        return mapping.user_sis
