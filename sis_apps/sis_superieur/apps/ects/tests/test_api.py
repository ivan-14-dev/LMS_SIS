"""API tests for ects."""

from django.test import SimpleTestCase
from django.urls import resolve


class EctsAPITestCase(SimpleTestCase):
    """Vérifie que le ViewSet `ects` est bien routé (et non un stub mort)."""

    def test_routes_are_registered(self):
        assert resolve("/api/v1/ects/bilans-ects/").url_name == "bilan-ects-list"
