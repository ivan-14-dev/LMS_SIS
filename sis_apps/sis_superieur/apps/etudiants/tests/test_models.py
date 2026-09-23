"""Model tests for etudiants."""

from apps.etudiants.models import Etudiant
from apps.integration.tests.tenant_test_case import TenantTestCase
from apps.utilisateurs.models import Utilisateur
from django.db import connection

TEST_USER_PASSWORD = "irrelevant-test-value-not-a-real-secret"


class EtudiantsModelTestCase(TenantTestCase):
    def _create_etudiant(self, **overrides):
        user = Utilisateur.objects.create_user(
            "etudiant_test", "etudiant_test@test.com", TEST_USER_PASSWORD, role="etudiant"
        )
        defaults = {
            "universite": self.tenant,
            "user": user,
            "matricule": "MAT-0001",
            "date_naissance": "2002-01-01",
            "lieu_naissance": "Paris",
            "sexe": "F",
            "adresse": "1 rue des Tests",
            "code_postal": "75000",
            "ville": "Paris",
            "telephone": "0100000000",
        }
        defaults.update(overrides)
        return Etudiant.objects.create(**defaults)

    def test_ssn_and_bank_details_are_encrypted_at_rest_and_decrypt_transparently(self):
        etudiant = self._create_etudiant(
            numero_securite_sociale="123456789012345",
            rib_iban="FR7630006000011234567890189",
        )

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT numero_securite_sociale, rib_iban "
                f"FROM {Etudiant._meta.db_table} WHERE id = %s",
                [etudiant.id],
            )
            raw_ssn, raw_rib_iban = cursor.fetchone()

        assert "123456789012345" not in raw_ssn
        assert "1234567890189" not in raw_rib_iban

        etudiant.refresh_from_db()
        assert etudiant.numero_securite_sociale == "123456789012345"
        assert etudiant.rib_iban == "FR7630006000011234567890189"

    def test_blank_sensitive_fields_stay_blank(self):
        etudiant = self._create_etudiant()

        etudiant.refresh_from_db()
        assert etudiant.numero_securite_sociale == ""
        assert etudiant.rib_iban == ""
