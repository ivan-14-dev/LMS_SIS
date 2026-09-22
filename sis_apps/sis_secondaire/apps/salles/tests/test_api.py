"""API tests for salles."""

from django.test import SimpleTestCase
from django.urls import resolve


class SallesAPITestCase(SimpleTestCase):
    """Vérifie que le ViewSet `salles` est bien routé (et non un stub mort)."""

    def test_routes_are_registered(self):
        assert resolve("/api/v1/salles/").url_name == "salle-list"
