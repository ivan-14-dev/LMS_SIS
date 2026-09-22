"""API tests for portail_parent."""

from django.test import SimpleTestCase
from django.urls import resolve


class PortailParentAPITestCase(SimpleTestCase):
    def test_tableau_bord_route_is_registered(self):
        match = resolve("/api/v1/portail/apprenant/tableau_bord/")

        assert match.url_name == "portail-apprenant-tableau-bord"

    def test_bulletins_route_is_registered(self):
        match = resolve("/api/v1/portail/apprenant/bulletins/")

        assert match.url_name == "portail-apprenant-bulletins"
