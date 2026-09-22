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
