"""API tests for transport."""

from django.test import SimpleTestCase
from django.urls import resolve


class TransportAPITestCase(SimpleTestCase):
    """Vérifie que les ViewSets `transport` sont bien routés (et non des stubs morts)."""

    def test_routes_are_registered(self):
        assert resolve("/api/v1/transport/lignes-transport/").url_name == "ligne-transport-list"
        assert resolve("/api/v1/transport/arrets/").url_name == "arret-list"
        assert resolve("/api/v1/transport/vehicules/").url_name == "vehicule-list"
        assert resolve("/api/v1/transport/inscriptions-transport/").url_name == "inscription-transport-list"
