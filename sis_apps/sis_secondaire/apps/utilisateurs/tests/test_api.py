"""API tests for utilisateurs - SIS Secondaire."""

from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.utilisateurs.models import Utilisateur
from rest_framework.authtoken.models import Token
from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)
from rest_framework_simplejwt.tokens import RefreshToken

TEST_USER_PASSWORD = "irrelevant-test-value-not-a-real-secret"


class SessionRevocationTestCase(TenantAPITestCase):
    """Tests de la révocation de session (token DRF + jetons JWT)."""

    def setUp(self):
        self.user = Utilisateur.objects.create_user(
            "revoke_self",
            "revoke_self@test.com",
            TEST_USER_PASSWORD,
            role="direction",
            etablissement=self.tenant,
        )
        self.other_user = Utilisateur.objects.create_user(
            "revoke_target",
            "revoke_target@test.com",
            TEST_USER_PASSWORD,
            role="eleve",
            etablissement=self.tenant,
        )

    def test_revoke_sessions_deletes_own_token(self):
        """L'action self-service supprime le token DRF de l'utilisateur connecté."""
        Token.objects.create(user=self.user)
        self.client.force_authenticate(user=self.user)

        response = self.client.post("/api/v1/utilisateurs/comptes/revoke_sessions/")

        assert response.status_code == 200
        assert response.data["token_revoked"] is True
        assert not Token.objects.filter(user=self.user).exists()

    def test_revoke_sessions_blacklists_outstanding_jwt_tokens(self):
        """L'action self-service blackliste les refresh tokens JWT actifs."""
        refresh = RefreshToken.for_user(self.user)
        outstanding = OutstandingToken.objects.get(jti=refresh["jti"])
        self.client.force_authenticate(user=self.user)

        response = self.client.post("/api/v1/utilisateurs/comptes/revoke_sessions/")

        assert response.status_code == 200
        assert response.data["jwt_tokens_revoked"] == 1
        assert BlacklistedToken.objects.filter(token=outstanding).exists()

    def test_change_password_revokes_existing_token(self):
        """Changer son mot de passe invalide le token DRF existant."""
        Token.objects.create(user=self.user)
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/api/v1/utilisateurs/comptes/change_password/",
            {"old_password": TEST_USER_PASSWORD, "new_password": "a-new-Strong-Passw0rd!"},
        )

        assert response.status_code == 200
        assert not Token.objects.filter(user=self.user).exists()

    def test_force_logout_by_admin_revokes_target_user_token(self):
        """Un administrateur (direction) peut révoquer les sessions d'un autre utilisateur."""
        Token.objects.create(user=self.other_user)
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            f"/api/v1/utilisateurs/comptes/{self.other_user.pk}/force_logout/"
        )

        assert response.status_code == 200
        assert response.data["token_revoked"] is True
        assert not Token.objects.filter(user=self.other_user).exists()

    def test_force_logout_requires_admin_permission(self):
        """Un élève ne peut pas révoquer les sessions d'un autre utilisateur."""
        Token.objects.create(user=self.user)
        self.client.force_authenticate(user=self.other_user)

        response = self.client.post(
            f"/api/v1/utilisateurs/comptes/{self.user.pk}/force_logout/"
        )

        assert response.status_code == 403
        assert Token.objects.filter(user=self.user).exists()

    def test_sessions_lists_own_outstanding_tokens(self):
        """La liste des sessions retourne les jetons JWT de l'utilisateur connecté."""
        refresh = RefreshToken.for_user(self.user)
        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/v1/utilisateurs/comptes/sessions/")

        assert response.status_code == 200
        assert len(response.data) == 1
        assert response.data[0]["jti"] == str(refresh["jti"])
        assert response.data[0]["revoked"] is False

    def test_sessions_does_not_leak_other_users_tokens(self):
        """Un utilisateur ne voit que ses propres sessions JWT."""
        RefreshToken.for_user(self.other_user)
        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/v1/utilisateurs/comptes/sessions/")

        assert response.status_code == 200
        assert response.data == []

    def test_revoke_session_blacklists_only_targeted_token(self):
        """Révoquer une session par `jti` ne blackliste que ce jeton précis."""
        refresh_a = RefreshToken.for_user(self.user)
        refresh_b = RefreshToken.for_user(self.user)
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/api/v1/utilisateurs/comptes/revoke_session/",
            {"jti": str(refresh_a["jti"])},
        )

        assert response.status_code == 200
        assert response.data["already_revoked"] is False
        outstanding_a = OutstandingToken.objects.get(jti=refresh_a["jti"])
        outstanding_b = OutstandingToken.objects.get(jti=refresh_b["jti"])
        assert BlacklistedToken.objects.filter(token=outstanding_a).exists()
        assert not BlacklistedToken.objects.filter(token=outstanding_b).exists()

    def test_revoke_session_rejects_unknown_or_foreign_jti(self):
        """Un utilisateur ne peut pas révoquer un jeton inexistant ou d'un tiers."""
        refresh_other = RefreshToken.for_user(self.other_user)
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/api/v1/utilisateurs/comptes/revoke_session/",
            {"jti": str(refresh_other["jti"])},
        )

        assert response.status_code == 404
        outstanding_other = OutstandingToken.objects.get(jti=refresh_other["jti"])
        assert not BlacklistedToken.objects.filter(token=outstanding_other).exists()


class MFAEnrollmentTestCase(TenantAPITestCase):
    """Tests de l'enrôlement MFA (TOTP) en deux temps."""

    def setUp(self):
        self.user = Utilisateur.objects.create_user(
            "mfa_user",
            "mfa_user@test.com",
            TEST_USER_PASSWORD,
            role="direction",
            etablissement=self.tenant,
        )

    def test_mfa_enroll_generates_secret_without_activating(self):
        """L'enrôlement génère un secret mais n'active pas encore le MFA."""
        self.client.force_authenticate(user=self.user)

        response = self.client.post("/api/v1/utilisateurs/comptes/mfa_enroll/")

        assert response.status_code == 200
        assert response.data["secret"]
        assert response.data["provisioning_uri"].startswith("otpauth://")
        self.user.refresh_from_db()
        assert self.user.mfa_secret == response.data["secret"]
        assert self.user.mfa_active is False

    def test_mfa_activate_with_valid_code_enables_mfa(self):
        """Un code TOTP valide confirme l'enrôlement et active le MFA."""
        import pyotp

        self.client.force_authenticate(user=self.user)
        self.client.post("/api/v1/utilisateurs/comptes/mfa_enroll/")
        self.user.refresh_from_db()
        code = pyotp.TOTP(self.user.mfa_secret).now()

        response = self.client.post(
            "/api/v1/utilisateurs/comptes/mfa_activate/", {"code": code}
        )

        assert response.status_code == 200
        assert response.data["mfa_active"] is True
        self.user.refresh_from_db()
        assert self.user.mfa_active is True

    def test_mfa_activate_with_invalid_code_fails(self):
        """Un code invalide ne doit pas activer le MFA."""
        self.client.force_authenticate(user=self.user)
        self.client.post("/api/v1/utilisateurs/comptes/mfa_enroll/")

        response = self.client.post(
            "/api/v1/utilisateurs/comptes/mfa_activate/", {"code": "000000"}
        )

        assert response.status_code == 400
        self.user.refresh_from_db()
        assert self.user.mfa_active is False

    def test_mfa_disable_requires_password_and_code(self):
        """La désactivation du MFA exige le mot de passe et un code TOTP valide."""
        import pyotp

        self.client.force_authenticate(user=self.user)
        self.client.post("/api/v1/utilisateurs/comptes/mfa_enroll/")
        self.user.refresh_from_db()
        code = pyotp.TOTP(self.user.mfa_secret).now()
        self.client.post("/api/v1/utilisateurs/comptes/mfa_activate/", {"code": code})
        self.user.refresh_from_db()
        new_code = pyotp.TOTP(self.user.mfa_secret).now()

        response = self.client.post(
            "/api/v1/utilisateurs/comptes/mfa_disable/",
            {"password": TEST_USER_PASSWORD, "code": new_code},
        )

        assert response.status_code == 200
        self.user.refresh_from_db()
        assert self.user.mfa_active is False
        assert self.user.mfa_secret == ""

    def test_mfa_disable_with_wrong_password_fails(self):
        """Un mauvais mot de passe empêche la désactivation du MFA."""
        import pyotp

        self.client.force_authenticate(user=self.user)
        self.client.post("/api/v1/utilisateurs/comptes/mfa_enroll/")
        self.user.refresh_from_db()
        code = pyotp.TOTP(self.user.mfa_secret).now()
        self.client.post("/api/v1/utilisateurs/comptes/mfa_activate/", {"code": code})

        response = self.client.post(
            "/api/v1/utilisateurs/comptes/mfa_disable/",
            {"password": "wrong-password", "code": code},
        )

        assert response.status_code == 400
        self.user.refresh_from_db()
        assert self.user.mfa_active is True


class MFALoginEnforcementTestCase(TenantAPITestCase):
    """Tests de l'application du MFA à la connexion (auth/token/)."""

    def setUp(self):
        self.user = Utilisateur.objects.create_user(
            "mfa_login_user",
            "mfa_login_user@test.com",
            TEST_USER_PASSWORD,
            role="direction",
            etablissement=self.tenant,
        )

    def test_login_without_mfa_active_does_not_require_code(self):
        """Sans MFA actif, la connexion classique fonctionne sans code."""
        response = self.client.post(
            "/api/v1/auth/token/",
            {"username": self.user.username, "password": TEST_USER_PASSWORD},
        )

        assert response.status_code == 200
        assert "access" in response.data

    def test_login_with_mfa_active_requires_valid_code(self):
        """Avec MFA actif, la connexion échoue sans code TOTP valide."""
        import pyotp

        secret = pyotp.random_base32()
        self.user.mfa_secret = secret
        self.user.mfa_active = True
        self.user.save(update_fields=["mfa_secret", "mfa_active"])

        response = self.client.post(
            "/api/v1/auth/token/",
            {"username": self.user.username, "password": TEST_USER_PASSWORD},
        )
        assert response.status_code == 400

        valid_response = self.client.post(
            "/api/v1/auth/token/",
            {
                "username": self.user.username,
                "password": TEST_USER_PASSWORD,
                "mfa_code": pyotp.TOTP(secret).now(),
            },
        )
        assert valid_response.status_code == 200
        assert "access" in valid_response.data


class PasswordResetTestCase(TenantAPITestCase):
    """Tests de la récupération de compte par email."""

    def setUp(self):
        from django.core.cache import cache

        # Ces endpoints sont accessibles anonymement et partagent le throttle
        # DRF "anon" (10/minute) avec le reste de l'API ; on repart d'un
        # compteur propre pour que les tests ne s'influencent pas entre eux.
        cache.clear()
        self.user = Utilisateur.objects.create_user(
            "reset_user",
            "reset_user@test.com",
            TEST_USER_PASSWORD,
            role="direction",
            etablissement=self.tenant,
        )

    def test_request_reset_sends_email_for_known_account(self):
        from django.core import mail

        response = self.client.post(
            "/api/v1/auth/password-reset/request/", {"email": self.user.email}
        )

        assert response.status_code == 200
        assert len(mail.outbox) == 1
        assert self.user.email in mail.outbox[0].to

    def test_request_reset_is_silent_for_unknown_email(self):
        """Ne doit pas permettre l'énumération de comptes : même réponse."""
        from django.core import mail

        response = self.client.post(
            "/api/v1/auth/password-reset/request/", {"email": "unknown@test.com"}
        )

        assert response.status_code == 200
        assert len(mail.outbox) == 0

    def test_confirm_reset_with_valid_token_changes_password(self):
        from django.contrib.auth.tokens import PasswordResetTokenGenerator
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode

        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = PasswordResetTokenGenerator().make_token(self.user)

        response = self.client.post(
            "/api/v1/auth/password-reset/confirm/",
            {"uid": uid, "token": token, "new_password": "a-new-Strong-Passw0rd!"},
        )

        assert response.status_code == 200
        self.user.refresh_from_db()
        assert self.user.check_password("a-new-Strong-Passw0rd!")

    def test_confirm_reset_with_invalid_token_fails(self):
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode

        uid = urlsafe_base64_encode(force_bytes(self.user.pk))

        response = self.client.post(
            "/api/v1/auth/password-reset/confirm/",
            {"uid": uid, "token": "invalid-token", "new_password": "a-new-Strong-Passw0rd!"},
        )

        assert response.status_code == 400
        self.user.refresh_from_db()
        assert self.user.check_password(TEST_USER_PASSWORD)
