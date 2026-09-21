"""API tests for structure."""

from django.test import SimpleTestCase
from django.urls import resolve


class StructureAPITestCase(SimpleTestCase):
    def test_structure_history_routes_are_registered(self):
        faculte_history = resolve("/api/v1/structure/facultes/1/historique/")
        departement_history = resolve("/api/v1/structure/departements/1/historique/")
        ecole_history = resolve("/api/v1/structure/ecoles-doctorales/1/historique/")

        self.assertEqual(faculte_history.url_name, "faculte-historique")
        self.assertEqual(departement_history.url_name, "departement-historique")
        self.assertEqual(ecole_history.url_name, "ecole-doctorale-historique")
