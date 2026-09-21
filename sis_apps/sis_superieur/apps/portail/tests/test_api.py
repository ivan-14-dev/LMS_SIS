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
            resolve("/api/v1/portail/apprenant/releves/").url_name,
            "portail-apprenant-releves",
        )

    def test_staff_routes_are_registered(self):
        self.assertEqual(
            resolve("/api/v1/portail/staff/tableau_bord/").url_name,
            "portail-staff-tableau-bord",
        )
        self.assertEqual(
            resolve("/api/v1/portail/staff/statistiques_formations/").url_name,
            "portail-staff-statistiques-formations",
        )
