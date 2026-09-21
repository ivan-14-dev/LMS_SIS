"""API tests for portail_etudiant."""

from django.test import SimpleTestCase
from django.urls import resolve


class PortailEtudiantAPITestCase(SimpleTestCase):
    def test_tableau_bord_route_is_registered(self):
        match = resolve("/api/v1/portail/etudiant/tableau_bord/")

        self.assertEqual(match.url_name, "portail-etudiant-tableau-bord")

    def test_factures_route_is_registered(self):
        match = resolve("/api/v1/portail/etudiant/factures/")

        self.assertEqual(match.url_name, "portail-etudiant-factures")
