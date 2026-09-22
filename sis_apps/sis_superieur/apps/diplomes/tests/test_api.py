"""API tests for diplomes."""

from django.test import SimpleTestCase
from django.urls import resolve


class DiplomesAPITestCase(SimpleTestCase):
    def test_diplome_routes_are_registered(self):
        list_match = resolve("/api/v1/diplomes/")
        detail_match = resolve("/api/v1/diplomes/1/")
        pdf_match = resolve("/api/v1/diplomes/1/pdf_officiel/")
        history_match = resolve("/api/v1/diplomes/1/historique/")
        catalogue_match = resolve("/api/v1/diplomes/catalogue/")

        assert list_match.url_name == "diplome-list"
        assert detail_match.url_name == "diplome-detail"
        assert pdf_match.url_name == "diplome-pdf-officiel"
        assert history_match.url_name == "diplome-historique"
        assert catalogue_match.url_name == "diplome-catalogue-list"
