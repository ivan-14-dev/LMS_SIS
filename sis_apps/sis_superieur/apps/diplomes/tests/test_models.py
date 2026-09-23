"""Model tests for diplomes."""

from apps.diplomes.models import Diplome
from apps.formations.models import Formation
from apps.integration.tests.tenant_test_case import TenantTestCase
from apps.structure.models import Departement, Faculte


class DiplomesModelTestCase(TenantTestCase):
    def test_diplome_str_returns_nom(self):
        faculte = Faculte.objects.create(universite=self.tenant, nom="Sciences", code="FS")
        departement = Departement.objects.create(faculte=faculte, nom="Informatique", code="INFO")
        formation = Formation.objects.create(departement=departement, nom="Licence Informatique", code="LINFO")
        diplome = Diplome.objects.create(
            formation=formation,
            type="national",
            nom="Licence en Informatique",
            niveau_grade="Licence",
        )

        assert str(diplome) == "Licence en Informatique"
