"""API tests for bourses."""

from django.test import SimpleTestCase
from django.urls import resolve


class BoursesAPITestCase(SimpleTestCase):
    """Vérifie que les ViewSets `bourses` sont bien routés (et non des stubs morts)."""

    def test_routes_are_registered(self):
        assert resolve("/api/v1/bourses/types-bourses/").url_name == "type-bourse-list"
        assert resolve("/api/v1/bourses/demandes-bourses/").url_name == "demande-bourse-list"
        assert resolve("/api/v1/bourses/attributions-bourses/").url_name == "attribution-bourse-list"
        assert resolve("/api/v1/bourses/versements-bourses/").url_name == "versement-bourse-list"
