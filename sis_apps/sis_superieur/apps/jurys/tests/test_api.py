"""API tests for jurys."""

from django.test import SimpleTestCase
from django.urls import resolve


class JurysAPITestCase(SimpleTestCase):
    """Vérifie que les ViewSets `jurys` sont bien routés (et non des stubs morts)."""

    def test_routes_are_registered(self):
        assert resolve("/api/v1/jurys/jurys/").url_name == "jury-list"
        assert resolve("/api/v1/jurys/deliberations/").url_name == "deliberation-list"
        assert resolve("/api/v1/jurys/decisions-jury/").url_name == "decision-jury-list"
        assert resolve("/api/v1/jurys/decisions-globales/").url_name == "decision-globale-list"
