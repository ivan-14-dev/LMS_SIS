"""API tests for portail_enseignant."""

from django.test import SimpleTestCase
from django.urls import resolve


class PortailEnseignantAPITestCase(SimpleTestCase):
    def test_tableau_bord_route_is_registered(self):
        match = resolve("/api/v1/portail/enseignant/tableau_bord/")

        self.assertEqual(match.url_name, "portail-enseignant-tableau-bord")

    def test_etudiants_cours_route_is_registered(self):
        match = resolve("/api/v1/portail/enseignant/etudiants_cours/")

        self.assertEqual(match.url_name, "portail-enseignant-etudiants-cours")
