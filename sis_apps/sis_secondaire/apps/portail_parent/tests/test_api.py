"""API tests for portail_parent."""

from django.test import SimpleTestCase
from django.urls import resolve


class PortailParentAPITestCase(SimpleTestCase):
    def test_tableau_bord_route_is_registered(self):
        match = resolve("/api/v1/portail/parent/tableau_bord/")

        self.assertEqual(match.url_name, "portail-parent-tableau-bord")

    def test_notes_enfant_route_is_registered(self):
        match = resolve("/api/v1/portail/parent/notes_enfant/")

        self.assertEqual(match.url_name, "portail-parent-notes-enfant")
