"""Model tests for utilisateurs."""

from apps.integration.tests.tenant_test_case import TenantTestCase
from apps.utilisateurs.models import Utilisateur
from django.db import connection

TEST_USER_PASSWORD = "irrelevant-test-value-not-a-real-secret"


class UtilisateursModelTestCase(TenantTestCase):
    def test_mfa_secret_is_encrypted_at_rest_and_decrypts_transparently(self):
        user = Utilisateur.objects.create_user(
            "mfa_user", "mfa_user@test.com", TEST_USER_PASSWORD,
            role="scolarite",
            mfa_active=True,
            mfa_secret="JBSWY3DPEHPK3PXP",
        )

        with connection.cursor() as cursor:
            cursor.execute(
                f"SELECT mfa_secret FROM {Utilisateur._meta.db_table} WHERE id = %s",
                [user.id],
            )
            raw_value = cursor.fetchone()[0]

        assert raw_value != "JBSWY3DPEHPK3PXP"
        assert "JBSWY3DPEHPK3PXP" not in raw_value

        user.refresh_from_db()
        assert user.mfa_secret == "JBSWY3DPEHPK3PXP"

    def test_blank_mfa_secret_stays_blank(self):
        user = Utilisateur.objects.create_user(
            "no_mfa_user", "no_mfa_user@test.com", TEST_USER_PASSWORD,
            role="etudiant",
        )

        user.refresh_from_db()
        assert user.mfa_secret == ""
