"""API tests for portail_enseignant."""

from django.test import SimpleTestCase
from django.urls import resolve


class PortailEnseignantAPITestCase(SimpleTestCase):
    def test_tableau_bord_route_is_registered(self):
        match = resolve("/api/v1/portail/enseignant/tableau_bord/")

        self.assertEqual(match.url_name, "portail-enseignant-tableau-bord")

    def test_absences_a_saisir_route_is_registered(self):
        match = resolve("/api/v1/portail/enseignant/absences_a_saisir/")

        self.assertEqual(match.url_name, "portail-enseignant-absences-a-saisir")
