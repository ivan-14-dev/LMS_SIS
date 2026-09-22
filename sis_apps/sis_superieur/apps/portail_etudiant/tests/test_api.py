"""API tests for portail_etudiant."""

from django.test import SimpleTestCase
from django.urls import resolve


class PortailEtudiantAPITestCase(SimpleTestCase):
    def test_tableau_bord_route_is_registered(self):
        match = resolve("/api/v1/portail/apprenant/tableau_bord/")

        assert match.url_name == "portail-apprenant-tableau-bord"

    def test_releves_route_is_registered(self):
        match = resolve("/api/v1/portail/apprenant/releves/")

        assert match.url_name == "portail-apprenant-releves"
