"""API tests for portail_eleve."""

from django.test import SimpleTestCase
from django.urls import resolve


class PortailEleveAPITestCase(SimpleTestCase):
    def test_tableau_bord_route_is_registered(self):
        match = resolve("/api/v1/portail/eleve/tableau_bord/")

        self.assertEqual(match.url_name, "portail-eleve-tableau-bord")

    def test_absences_route_is_registered(self):
        match = resolve("/api/v1/portail/eleve/absences/")

        self.assertEqual(match.url_name, "portail-eleve-absences")
