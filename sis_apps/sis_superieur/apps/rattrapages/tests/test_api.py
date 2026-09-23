"""API tests for rattrapages."""

from django.test import SimpleTestCase
from django.urls import resolve


class RattrapagesAPITestCase(SimpleTestCase):
    """Vérifie que le ViewSet `rattrapages` est bien routé (et non un stub mort)."""

    def test_routes_are_registered(self):
        assert resolve("/api/v1/rattrapages/").url_name == "inscription-rattrapage-list"
