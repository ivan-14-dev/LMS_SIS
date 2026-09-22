"""API tests for memoires."""

from django.test import SimpleTestCase
from django.urls import resolve


class MemoiresAPITestCase(SimpleTestCase):
    """Vérifie que les ViewSets `memoires` sont bien routés (et non des stubs morts)."""

    def test_routes_are_registered(self):
        assert resolve("/api/v1/memoires/sujets-memoire/").url_name == "sujet-memoire-list"
        assert resolve("/api/v1/memoires/").url_name == "memoire-list"
        assert resolve("/api/v1/memoires/jurys-memoire/").url_name == "jury-memoire-list"
