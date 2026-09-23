"""API tests for recherche."""

from django.test import SimpleTestCase
from django.urls import resolve


class RechercheAPITestCase(SimpleTestCase):
    """Vérifie que les ViewSets `recherche` sont bien routés (et non des stubs morts)."""

    def test_routes_are_registered(self):
        assert resolve("/api/v1/recherche/laboratoires/").url_name == "laboratoire-list"
        assert resolve("/api/v1/recherche/projets-recherche/").url_name == "projet-recherche-list"
        assert (
            resolve("/api/v1/recherche/productions-scientifiques/").url_name
            == "production-scientifique-list"
        )
        assert resolve("/api/v1/recherche/theses/").url_name == "these-list"
