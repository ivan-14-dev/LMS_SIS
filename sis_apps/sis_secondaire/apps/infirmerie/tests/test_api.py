"""API tests for infirmerie."""

from django.test import SimpleTestCase
from django.urls import resolve


class InfirmerieAPITestCase(SimpleTestCase):
    """Vérifie que les ViewSets `infirmerie` sont bien routés (et non des stubs morts)."""

    def test_routes_are_registered(self):
        assert resolve("/api/v1/infirmerie/dossiers-medicaux/").url_name == "dossier-medical-list"
        assert resolve("/api/v1/infirmerie/visites-infirmerie/").url_name == "visite-infirmerie-list"
        assert resolve("/api/v1/infirmerie/stock-medicaments/").url_name == "stock-medicament-list"
