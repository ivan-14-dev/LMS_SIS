"""Model tests for classes."""

import datetime

from apps.classes.models import Classe, Groupe
from apps.etablissement.models import AnneeScolaire, Niveau
from apps.integration.tests.tenant_test_case import TenantTestCase


class ClassesModelTestCase(TenantTestCase):
    def setUp(self):
        self.annee = AnneeScolaire.objects.create(
            etablissement=self.tenant,
            libelle="2026-2027",
            date_debut=datetime.date(2026, 9, 1),
            date_fin=datetime.date(2027, 6, 30),
        )
        self.niveau = Niveau.objects.create(
            etablissement=self.tenant,
            code="6e",
            libelle="6ème",
            ordre=1,
        )

    def test_classe_str_includes_nom_and_annee_scolaire(self):
        classe = Classe.objects.create(
            etablissement=self.tenant,
            annee_scolaire=self.annee,
            niveau=self.niveau,
            nom="6e A",
        )

        assert str(classe) == "6e A (2026-2027)"

    def test_classe_effectif_actuel_defaults_to_zero(self):
        classe = Classe.objects.create(
            etablissement=self.tenant,
            annee_scolaire=self.annee,
            niveau=self.niveau,
            nom="6e B",
        )

        assert classe.effectif_actuel == 0

    def test_groupe_str_includes_nom_and_type_display(self):
        groupe = Groupe.objects.create(
            etablissement=self.tenant,
            annee_scolaire=self.annee,
            nom="Anglais LV1",
            type="langue",
        )

        assert str(groupe) == "Anglais LV1 (Langue)"
