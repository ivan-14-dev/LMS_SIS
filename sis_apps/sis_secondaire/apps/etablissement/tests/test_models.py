"""Model tests for etablissement."""

import datetime

from apps.etablissement.models import AnneeScolaire, Niveau, Periode
from apps.integration.tests.tenant_test_case import TenantTestCase


class EtablissementModelTestCase(TenantTestCase):
    def test_annee_scolaire_str_returns_libelle(self):
        annee = AnneeScolaire.objects.create(
            etablissement=self.tenant,
            libelle="2026-2027",
            date_debut=datetime.date(2026, 9, 1),
            date_fin=datetime.date(2027, 6, 30),
        )

        assert str(annee) == "2026-2027"

    def test_periode_str_includes_type_and_annee_scolaire(self):
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

        assert str(periode) == "Trimestre 1 - 2026-2027"

    def test_niveau_str_returns_libelle(self):
        niveau = Niveau.objects.create(
            etablissement=self.tenant,
            code="6e",
            libelle="6ème",
            ordre=1,
        )

        assert str(niveau) == "6ème"
