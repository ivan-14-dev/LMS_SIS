"""API tests for formations."""

from django.test import SimpleTestCase
from django.urls import resolve


class FormationsAPITestCase(SimpleTestCase):
    def test_formation_history_routes_are_registered(self):
        formation_history = resolve("/api/v1/formations/formations/1/historique/")
        parcours_history = resolve("/api/v1/formations/parcours/1/historique/")
        maquette_history = resolve("/api/v1/formations/maquettes/1/historique/")

        assert formation_history.url_name == "formation-historique"
        assert parcours_history.url_name == "parcours-historique"
        assert maquette_history.url_name == "maquette-historique"
