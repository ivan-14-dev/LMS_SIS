"""Model tests for conseil de classe."""

import datetime

from apps.classes.models import Classe
from apps.conseil_classe.models import AppreciationConseil, ConseilClasse, DecisionConseil
from apps.eleves.models import Eleve
from apps.etablissement.models import AnneeScolaire, Niveau, Periode
from apps.integration.tests.tenant_test_case import TenantTestCase
from apps.utilisateurs.models import Utilisateur

TEST_USER_PASSWORD = "irrelevant-test-value-not-a-real-secret"


class ConseilClasseModelTestCase(TenantTestCase):
    def setUp(self):
        self.annee = AnneeScolaire.objects.create(
            etablissement=self.tenant,
            libelle="2026-2027",
            date_debut=datetime.date(2026, 9, 1),
            date_fin=datetime.date(2027, 6, 30),
        )
        self.niveau = Niveau.objects.create(
            etablissement=self.tenant, code="6e", libelle="6ème", ordre=1
        )
        self.classe = Classe.objects.create(
            etablissement=self.tenant,
            annee_scolaire=self.annee,
            niveau=self.niveau,
            nom="6e A",
        )
        self.periode = Periode.objects.create(
            annee_scolaire=self.annee,
            type="trimestre",
            numero=1,
            date_debut=datetime.date(2026, 9, 1),
            date_fin=datetime.date(2026, 12, 20),
        )
        self.president = Utilisateur.objects.create_user(
            "conseil_president",
            "conseil_president@test.com",
            TEST_USER_PASSWORD,
            role="direction",
            etablissement=self.tenant,
        )
        self.conseil = ConseilClasse.objects.create(
            classe=self.classe,
            periode=self.periode,
            date="2026-12-15T09:00:00Z",
            president=self.president,
        )

    def test_conseil_classe_str_includes_classe_and_periode(self):
        assert str(self.conseil) == f"Conseil {self.classe} - {self.periode}"

    def test_decision_conseil_str_includes_eleve_and_decision_display(self):
        eleve_user = Utilisateur.objects.create_user(
            "eleve_conseil",
            "eleve_conseil@test.com",
            TEST_USER_PASSWORD,
            role="eleve",
            etablissement=self.tenant,
        )
        eleve = Eleve.objects.create(
            etablissement=self.tenant,
            user=eleve_user,
            matricule="MAT-001",
            date_naissance=datetime.date(2012, 1, 1),
            lieu_naissance="Paris",
            sexe="M",
            date_inscription=datetime.date(2026, 9, 1),
        )
        decision = DecisionConseil.objects.create(
            conseil=self.conseil,
            eleve=eleve,
            decision="passage",
        )

        assert str(decision) == f"{eleve} : Passage en classe supérieure"

    def test_appreciation_conseil_str_includes_eleve_and_conseil(self):
        eleve_user = Utilisateur.objects.create_user(
            "eleve_conseil_2",
            "eleve_conseil_2@test.com",
            TEST_USER_PASSWORD,
            role="eleve",
            etablissement=self.tenant,
        )
        eleve = Eleve.objects.create(
            etablissement=self.tenant,
            user=eleve_user,
            matricule="MAT-002",
            date_naissance=datetime.date(2012, 1, 1),
            lieu_naissance="Paris",
            sexe="F",
            date_inscription=datetime.date(2026, 9, 1),
        )
        appreciation = AppreciationConseil.objects.create(
            conseil=self.conseil,
            eleve=eleve,
            appreciation="Bon trimestre.",
        )

        assert str(appreciation) == f"Appréciation {eleve} - {self.conseil}"
