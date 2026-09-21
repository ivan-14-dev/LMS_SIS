"""API tests for bulletins."""

from django.test import SimpleTestCase
from django.urls import resolve


class BulletinsAPITestCase(SimpleTestCase):
    def test_bulletin_routes_are_registered(self):
        list_match = resolve("/api/v1/bulletins/")
        detail_match = resolve("/api/v1/bulletins/1/")
        pdf_match = resolve("/api/v1/bulletins/1/pdf_officiel/")
        history_match = resolve("/api/v1/bulletins/1/historique/")
        appreciations_match = resolve("/api/v1/bulletins/appreciations/")

        self.assertEqual(list_match.url_name, "bulletin-list")
        self.assertEqual(detail_match.url_name, "bulletin-detail")
        self.assertEqual(pdf_match.url_name, "bulletin-pdf-officiel")
        self.assertEqual(history_match.url_name, "bulletin-historique")
        self.assertEqual(appreciations_match.url_name, "appreciation-matiere-list")
