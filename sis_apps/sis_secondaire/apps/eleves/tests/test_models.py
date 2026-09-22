"""Model tests for eleves."""

from apps.eleves.models import Eleve
from apps.integration.tests.tenant_test_case import TenantTestCase
from apps.utilisateurs.models import Utilisateur
from django.db import connection

TEST_USER_PASSWORD = "irrelevant-test-value-not-a-real-secret"


class ElevesModelTestCase(TenantTestCase):
    def _create_eleve(self, **overrides):
        user = Utilisateur.objects.create_user(
            "eleve_test", "eleve_test@test.com", TEST_USER_PASSWORD, role="eleve"
        )
        defaults = {
            "etablissement": self.tenant,
            "user": user,
            "matricule": "MAT-0001",
            "date_naissance": "2008-01-01",
            "lieu_naissance": "Paris",
            "sexe": "F",
            "date_inscription": "2023-09-01",
        }
        defaults.update(overrides)
        return Eleve.objects.create(**defaults)

    def test_allergies_are_encrypted_at_rest_and_decrypt_transparently(self):
        eleve = self._create_eleve(allergies="Allergie sévère aux arachides")

        with connection.cursor() as cursor:
            cursor.execute(
                f"SELECT allergies FROM {Eleve._meta.db_table} WHERE id = %s",
                [eleve.id],
            )
            raw_value = cursor.fetchone()[0]

        assert "arachides" not in raw_value

        eleve.refresh_from_db()
        assert eleve.allergies == "Allergie sévère aux arachides"

    def test_blank_allergies_stay_blank(self):
        eleve = self._create_eleve()

        eleve.refresh_from_db()
        assert eleve.allergies == ""
