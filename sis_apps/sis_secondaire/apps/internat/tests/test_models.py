"""Model tests for internat."""

from apps.integration.tests.tenant_test_case import TenantTestCase
from apps.internat.models import BatimentInternat, Chambre


class InternatModelTestCase(TenantTestCase):
    def test_batiment_str_returns_nom(self):
        batiment = BatimentInternat.objects.create(nom="Bâtiment A", nb_etages=3)

        assert str(batiment) == "Bâtiment A"

    def test_chambre_str_includes_batiment_and_numero(self):
        batiment = BatimentInternat.objects.create(nom="Bâtiment A")
        chambre = Chambre.objects.create(batiment=batiment, numero="101", type="double")

        assert str(chambre) == "Bâtiment A - Chambre 101"
