"""API tests for portail_doyen."""

from django.test import SimpleTestCase
from django.urls import resolve


class PortailDoyenAPITestCase(SimpleTestCase):
    def test_tableau_bord_route_is_registered(self):
        match = resolve("/api/v1/portail/doyen/tableau_bord/")

        self.assertEqual(match.url_name, "portail-doyen-tableau-bord")

    def test_budget_route_is_registered(self):
        match = resolve("/api/v1/portail/doyen/budget/")

        self.assertEqual(match.url_name, "portail-doyen-budget")
