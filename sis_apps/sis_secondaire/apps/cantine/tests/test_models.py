"""Model tests for cantine."""

from apps.cantine.models import InscriptionCantine
from apps.eleves.models import Eleve
from apps.integration.tests.tenant_test_case import TenantTestCase
from apps.utilisateurs.models import Utilisateur
from django.db import connection

TEST_USER_PASSWORD = "irrelevant-test-value-not-a-real-secret"


class CantineModelTestCase(TenantTestCase):
    def _create_inscription(self, **overrides):
        user = Utilisateur.objects.create_user(
            "cantine_eleve", "cantine_eleve@test.com", TEST_USER_PASSWORD, role="eleve"
        )
        eleve = Eleve.objects.create(
            etablissement=self.tenant,
            user=user,
            matricule="MAT-0002",
            date_naissance="2009-01-01",
            lieu_naissance="Lyon",
            sexe="M",
            date_inscription="2023-09-01",
        )
        defaults = {"eleve": eleve, "date_debut": "2023-09-01"}
        defaults.update(overrides)
        return InscriptionCantine.objects.create(**defaults)

    def test_allergies_are_encrypted_at_rest_and_decrypt_transparently(self):
        inscription = self._create_inscription(allergies=["arachides", "lactose"])

        with connection.cursor() as cursor:
            cursor.execute(
                f"SELECT allergies FROM {InscriptionCantine._meta.db_table} WHERE id = %s",
                [inscription.id],
            )
            raw_value = cursor.fetchone()[0]

        assert "arachides" not in raw_value

        inscription.refresh_from_db()
        assert inscription.allergies == ["arachides", "lactose"]

    def test_default_allergies_is_empty_list(self):
        inscription = self._create_inscription()

        inscription.refresh_from_db()
        assert inscription.allergies == []
