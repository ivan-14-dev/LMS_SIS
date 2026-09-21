"""API tests for consolidated portail."""

from django.test import SimpleTestCase
from django.urls import resolve


class PortailAPITestCase(SimpleTestCase):
    def test_apprenant_routes_are_registered(self):
        self.assertEqual(
            resolve("/api/v1/portail/apprenant/tableau_bord/").url_name,
            "portail-apprenant-tableau-bord",
        )
        self.assertEqual(
            resolve("/api/v1/portail/apprenant/bulletins/").url_name,
            "portail-apprenant-bulletins",
        )

    def test_staff_routes_are_registered(self):
        self.assertEqual(
            resolve("/api/v1/portail/staff/tableau_bord/").url_name,
            "portail-staff-tableau-bord",
        )
        self.assertEqual(
            resolve("/api/v1/portail/staff/absences_a_saisir/").url_name,
            "portail-staff-absences-a-saisir",
        )
