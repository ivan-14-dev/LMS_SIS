"""API tests for portail_enseignant."""

from django.test import SimpleTestCase
from django.urls import resolve


class PortailEnseignantAPITestCase(SimpleTestCase):
    def test_tableau_bord_route_is_registered(self):
        match = resolve("/api/v1/portail/staff/tableau_bord/")

        self.assertEqual(match.url_name, "portail-staff-tableau-bord")

    def test_absences_a_saisir_route_is_registered(self):
        match = resolve("/api/v1/portail/staff/absences_a_saisir/")

        self.assertEqual(match.url_name, "portail-staff-absences-a-saisir")
