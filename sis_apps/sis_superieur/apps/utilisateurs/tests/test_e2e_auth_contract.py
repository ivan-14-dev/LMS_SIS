"""Tests de contrat E2E pour les parcours d'authentification.

Contrairement aux tests unitaires de `test_api.py` (qui vérifient chaque
action isolément), ces tests exercent un parcours utilisateur complet en
enchaînant plusieurs appels HTTP réels via l'`APIClient` DRF, et vérifient
la forme exacte (contrat) des réponses JSON à chaque étape. Ils garantissent
que la chaîne complète — récupération de compte, connexion, enrôlement
MFA, connexion avec MFA — continue de fonctionner de bout en bout après
toute modification future de l'une de ces briques.
"""

import pyotp
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.utilisateurs.models import Utilisateur
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core import mail
from django.core.cache import cache
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

TEST_USER_PASSWORD = "irrelevant-test-value-not-a-real-secret"


class AccountRecoveryToMFAContractTestCase(TenantAPITestCase):
    """Parcours complet : mot de passe oublié -> connexion -> enrôlement MFA."""

    def setUp(self):
        cache.clear()
        self.user = Utilisateur.objects.create_user(
            "e2e_user",
            "e2e_user@test.com",
            TEST_USER_PASSWORD,
            role="doyen",
            etablissement=self.tenant,
        )

    def test_full_recovery_login_and_mfa_enrollment_journey(self):
        # 1. L'utilisateur a oublié son mot de passe : il demande un lien.
        request_response = self.client.post(
            "/api/v1/auth/password-reset/request/", {"email": self.user.email}
        )
        assert request_response.status_code == 200
        assert set(request_response.data.keys()) == {"detail"}
        assert len(mail.outbox) == 1
        reset_email = mail.outbox[0]
        assert self.user.email in reset_email.to
        assert "reset-password" in reset_email.body

        # 2. Il clique sur le lien et choisit un nouveau mot de passe.
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = PasswordResetTokenGenerator().make_token(self.user)
        new_password = "Another-Strong-Passw0rd!"
        confirm_response = self.client.post(
            "/api/v1/auth/password-reset/confirm/",
            {"uid": uid, "token": token, "new_password": new_password},
        )
        assert confirm_response.status_code == 200
        assert set(confirm_response.data.keys()) == {"detail"}

        # 3. Il se connecte avec son nouveau mot de passe (pas encore de MFA).
        login_response = self.client.post(
            "/api/v1/auth/token/",
            {"username": self.user.username, "password": new_password},
        )
        assert login_response.status_code == 200
        assert {"access", "refresh"} <= set(login_response.data.keys())
        access_token = login_response.data["access"]

        # 4. Authentifié, il démarre l'enrôlement MFA.
        auth_header = "Bearer " + access_token
        self.client.credentials(HTTP_AUTHORIZATION=auth_header)
        enroll_response = self.client.post("/api/v1/utilisateurs/comptes/mfa_enroll/")
        assert enroll_response.status_code == 200
        assert set(enroll_response.data.keys()) == {"secret", "provisioning_uri", "detail"}
        secret = enroll_response.data["secret"]

        # 5. Il confirme l'enrôlement avec un vrai code TOTP généré à partir du secret.
        code = pyotp.TOTP(secret).now()
        activate_response = self.client.post(
            "/api/v1/utilisateurs/comptes/mfa_activate/", {"code": code}
        )
        assert activate_response.status_code == 200
        assert activate_response.data["mfa_active"] is True

        # 6. Une future connexion sans code MFA doit désormais échouer...
        self.client.credentials()  # repart sans jeton, comme un nouveau login
        relogin_without_code = self.client.post(
            "/api/v1/auth/token/",
            {"username": self.user.username, "password": new_password},
        )
        assert relogin_without_code.status_code == 400

        # ...et réussir avec un code TOTP valide.
        relogin_with_code = self.client.post(
            "/api/v1/auth/token/",
            {
                "username": self.user.username,
                "password": new_password,
                "mfa_code": pyotp.TOTP(secret).now(),
            },
        )
        assert relogin_with_code.status_code == 200
        assert {"access", "refresh"} <= set(relogin_with_code.data.keys())
