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

        assert list_match.url_name == "bulletin-list"
        assert detail_match.url_name == "bulletin-detail"
        assert pdf_match.url_name == "bulletin-pdf-officiel"
        assert history_match.url_name == "bulletin-historique"
        assert appreciations_match.url_name == "appreciation-matiere-list"
