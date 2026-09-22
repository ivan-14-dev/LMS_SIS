"""API tests for maquettes."""

from django.test import SimpleTestCase
from django.urls import resolve


class MaquettesAPITestCase(SimpleTestCase):
    """Vérifie que le ViewSet `maquettes` est bien routé (et non un stub mort)."""

    def test_routes_are_registered(self):
        assert resolve("/api/v1/maquettes/").url_name == "maquette-list"
