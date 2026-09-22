"""Model tests for structure."""

from apps.integration.tests.tenant_test_case import TenantTestCase
from apps.structure.models import Departement, Faculte


class StructureModelTestCase(TenantTestCase):
    def test_faculte_str_includes_code_and_nom(self):
        faculte = Faculte.objects.create(
            universite=self.tenant, nom="Sciences et Technologies", code="FST"
        )

        assert str(faculte) == "FST - Sciences et Technologies"

    def test_departement_str_includes_code_and_nom(self):
        faculte = Faculte.objects.create(
            universite=self.tenant, nom="Sciences et Technologies", code="FST"
        )
        departement = Departement.objects.create(
            faculte=faculte, nom="Informatique", code="INFO"
        )

        assert str(departement) == "INFO - Informatique"
