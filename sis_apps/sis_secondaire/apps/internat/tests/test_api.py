"""API tests for internat."""

from django.test import SimpleTestCase
from django.urls import resolve


class InternatAPITestCase(SimpleTestCase):
    """Vérifie que les ViewSets `internat` sont bien routés (et non des stubs morts)."""

    def test_routes_are_registered(self):
        assert resolve("/api/v1/internat/batiments/").url_name == "batiment-internat-list"
        assert resolve("/api/v1/internat/chambres/").url_name == "chambre-list"
        assert resolve("/api/v1/internat/occupants-chambres/").url_name == "occupant-chambre-list"
        assert resolve("/api/v1/internat/etudes-surveillees/").url_name == "etude-surveillee-list"
