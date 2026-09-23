"""Model tests for bourses."""

from apps.bourses.models import AttributionBourse, DemandeBourse, TypeBourse
from apps.etablissement.models import AnneeUniversitaire
from apps.etudiants.models import Etudiant
from apps.integration.tests.tenant_test_case import TenantTestCase
from apps.utilisateurs.models import Utilisateur
from django.db import connection

TEST_USER_PASSWORD = "irrelevant-test-value-not-a-real-secret"


class BoursesModelTestCase(TenantTestCase):
    def _create_attribution(self, **overrides):
        user = Utilisateur.objects.create_user(
            "boursier_test", "boursier_test@test.com", TEST_USER_PASSWORD, role="etudiant"
        )
        etudiant = Etudiant.objects.create(
            universite=self.tenant,
            user=user,
            matricule="MAT-BOURSE-0001",
            date_naissance="2002-01-01",
            lieu_naissance="Paris",
            sexe="F",
            adresse="1 rue des Tests",
            code_postal="75000",
            ville="Paris",
            telephone="0100000000",
        )
        type_bourse = TypeBourse.objects.create(
            nom="Bourse au mérite", categorie="merite", montant_mensuel="150.00"
        )
        annee = AnneeUniversitaire.objects.create(
            universite=self.tenant,
            libelle="2023-2024",
            date_debut="2023-09-01",
            date_fin="2024-06-30",
        )
        demande = DemandeBourse.objects.create(
            etudiant=etudiant, type_bourse=type_bourse, annee_universitaire=annee
        )
        defaults = {
            "demande": demande,
            "numero_attribution": "ATTR-0001",
            "date_debut": "2023-09-01",
            "date_fin": "2024-06-30",
            "montant_mensuel": "150.00",
            "montant_total": "1500.00",
        }
        defaults.update(overrides)
        return AttributionBourse.objects.create(**defaults)

    def test_rib_iban_is_encrypted_at_rest_and_decrypts_transparently(self):
        attribution = self._create_attribution(rib_iban="FR7630006000011234567890189")

        with connection.cursor() as cursor:
            cursor.execute(
                f"SELECT rib_iban FROM {AttributionBourse._meta.db_table} WHERE id = %s",
                [attribution.id],
            )
            raw_value = cursor.fetchone()[0]

        assert "1234567890189" not in raw_value

        attribution.refresh_from_db()
        assert attribution.rib_iban == "FR7630006000011234567890189"

    def test_blank_rib_iban_stays_blank(self):
        attribution = self._create_attribution()

        attribution.refresh_from_db()
        assert attribution.rib_iban == ""
