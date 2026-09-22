"""API tests for cantine."""

from django.test import SimpleTestCase
from django.urls import resolve


class CantineAPITestCase(SimpleTestCase):
    """Vérifie que les ViewSets `cantine` sont bien routés (et non des stubs morts)."""

    def test_routes_are_registered(self):
        assert resolve("/api/v1/cantine/menus/").url_name == "menu-list"
        assert resolve("/api/v1/cantine/inscriptions-cantine/").url_name == "inscription-cantine-list"
        assert resolve("/api/v1/cantine/presences-cantine/").url_name == "presence-cantine-list"
