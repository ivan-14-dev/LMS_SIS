"""Model tests for bulletins."""

import datetime

from apps.bulletins.models import AppreciationMatiere
from apps.classes.models import Matiere
from apps.eleves.models import Eleve
from apps.etablissement.models import AnneeScolaire, Periode
from apps.integration.tests.tenant_test_case import TenantTestCase
from apps.utilisateurs.models import Utilisateur

TEST_USER_PASSWORD = "irrelevant-test-value-not-a-real-secret"


class BulletinsModelTestCase(TenantTestCase):
    def test_appreciation_matiere_str_includes_eleve_matiere_periode(self):
        annee = AnneeScolaire.objects.create(
            etablissement=self.tenant,
            libelle="2026-2027",
            date_debut=datetime.date(2026, 9, 1),
            date_fin=datetime.date(2027, 6, 30),
        )
        periode = Periode.objects.create(
            annee_scolaire=annee,
            type="trimestre",
            numero=1,
            date_debut=datetime.date(2026, 9, 1),
            date_fin=datetime.date(2026, 12, 20),
        )
        matiere = Matiere.objects.create(etablissement=self.tenant, code="MATH", nom="Mathématiques")
        eleve_user = Utilisateur.objects.create_user(
            "eleve_bulletin",
            "eleve_bulletin@test.com",
            TEST_USER_PASSWORD,
            role="eleve",
            etablissement=self.tenant,
        )
        eleve = Eleve.objects.create(
            etablissement=self.tenant,
            user=eleve_user,
            matricule="MAT-BULL-001",
            date_naissance=datetime.date(2012, 1, 1),
            lieu_naissance="Paris",
            sexe="M",
            date_inscription=datetime.date(2026, 9, 1),
        )
        appreciation = AppreciationMatiere.objects.create(
            eleve=eleve,
            matiere=matiere,
            periode=periode,
            appreciation="Bon travail.",
        )

        assert str(appreciation) == f"{eleve} - {matiere} - {periode}"
