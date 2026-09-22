"""Model tests for enseignants."""

from apps.enseignants.models import Personnel
from apps.integration.tests.tenant_test_case import TenantTestCase
from apps.utilisateurs.models import Utilisateur
from django.db import connection

TEST_USER_PASSWORD = "irrelevant-test-value-not-a-real-secret"


class EnseignantsModelTestCase(TenantTestCase):
    def _create_personnel(self, **overrides):
        user = Utilisateur.objects.create_user(
            "personnel_test", "personnel_test@test.com", TEST_USER_PASSWORD, role="enseignant"
        )
        defaults = {
            "user": user,
            "matricule": "PERS-0001",
            "date_embauche": "2020-09-01",
        }
        defaults.update(overrides)
        return Personnel.objects.create(**defaults)

    def test_rib_and_iban_are_encrypted_at_rest_and_decrypt_transparently(self):
        personnel = self._create_personnel(
            rib="30006000011234567890189", iban="FR7630006000011234567890189"
        )

        with connection.cursor() as cursor:
            cursor.execute(
                f"SELECT rib, iban FROM {Personnel._meta.db_table} WHERE id = %s",
                [personnel.id],
            )
            raw_rib, raw_iban = cursor.fetchone()

        assert "1234567890189" not in raw_rib
        assert "1234567890189" not in raw_iban

        personnel.refresh_from_db()
        assert personnel.rib == "30006000011234567890189"
        assert personnel.iban == "FR7630006000011234567890189"

    def test_blank_bank_fields_stay_blank(self):
        personnel = self._create_personnel()

        personnel.refresh_from_db()
        assert personnel.rib == ""
        assert personnel.iban == ""
