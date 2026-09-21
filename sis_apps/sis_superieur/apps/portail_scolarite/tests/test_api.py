"""API tests for portail_scolarite."""

from django.test import SimpleTestCase
from django.urls import resolve


class PortailScolariteAPITestCase(SimpleTestCase):
    def test_tableau_bord_route_is_registered(self):
        match = resolve("/api/v1/portail/scolarite/tableau_bord/")

        self.assertEqual(match.url_name, "portail-scolarite-tableau-bord")

    def test_dossier_etudiant_route_is_registered(self):
        match = resolve("/api/v1/portail/scolarite/dossier_etudiant/")

        self.assertEqual(match.url_name, "portail-scolarite-dossier-etudiant")
