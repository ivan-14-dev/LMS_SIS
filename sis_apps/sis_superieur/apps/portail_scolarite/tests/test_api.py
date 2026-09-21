"""API tests for portail_scolarite."""

from django.test import SimpleTestCase
from django.urls import resolve


class PortailScolariteAPITestCase(SimpleTestCase):
    def test_tableau_bord_route_is_registered(self):
        match = resolve("/api/v1/portail/staff/tableau_bord/")

        self.assertEqual(match.url_name, "portail-staff-tableau-bord")

    def test_alertes_route_is_registered(self):
        match = resolve("/api/v1/portail/staff/alertes/")

        self.assertEqual(match.url_name, "portail-staff-alertes")
