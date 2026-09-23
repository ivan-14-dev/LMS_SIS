"""Model tests for infirmerie."""

from apps.eleves.models import Eleve
from apps.infirmerie.models import DossierMedical
from apps.integration.tests.tenant_test_case import TenantTestCase
from apps.utilisateurs.models import Utilisateur
from django.db import connection

TEST_USER_PASSWORD = "irrelevant-test-value-not-a-real-secret"


class InfirmerieModelTestCase(TenantTestCase):
    def _create_eleve(self):
        user = Utilisateur.objects.create_user(
            "infirmerie_eleve", "infirmerie_eleve@test.com", TEST_USER_PASSWORD, role="eleve"
        )
        return Eleve.objects.create(
            etablissement=self.tenant,
            user=user,
            matricule="MAT-0003",
            date_naissance="2010-01-01",
            lieu_naissance="Marseille",
            sexe="F",
            date_inscription="2023-09-01",
        )

    def test_medical_data_is_encrypted_at_rest_and_decrypts_transparently(self):
        dossier = DossierMedical.objects.create(
            eleve=self._create_eleve(),
            groupe_sanguin="O+",
            allergies=["pollen", "arachides"],
            maladies_chroniques=["asthme"],
            traitements="Ventoline en cas de crise",
            vaccinations=["DTP", "ROR"],
            observations="Suivi renforcé recommandé",
        )

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT groupe_sanguin, allergies, maladies_chroniques, traitements, "
                f"vaccinations, observations FROM {DossierMedical._meta.db_table} WHERE id = %s",
                [dossier.id],
            )
            row = cursor.fetchone()

        raw_groupe_sanguin, raw_allergies, raw_maladies, raw_traitements, raw_vaccinations, raw_observations = row
        assert raw_groupe_sanguin != "O+"
        assert "arachides" not in raw_allergies
        assert "asthme" not in raw_maladies
        assert "Ventoline" not in raw_traitements
        assert "ROR" not in raw_vaccinations
        assert "renforcé" not in raw_observations

        dossier.refresh_from_db()
        assert dossier.groupe_sanguin == "O+"
        assert dossier.allergies == ["pollen", "arachides"]
        assert dossier.maladies_chroniques == ["asthme"]
        assert dossier.traitements == "Ventoline en cas de crise"
        assert dossier.vaccinations == ["DTP", "ROR"]
        assert dossier.observations == "Suivi renforcé recommandé"

    def test_default_json_fields_are_empty_lists(self):
        dossier = DossierMedical.objects.create(eleve=self._create_eleve())

        dossier.refresh_from_db()
        assert dossier.allergies == []
        assert dossier.maladies_chroniques == []
        assert dossier.vaccinations == []
