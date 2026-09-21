"""API tests for diplomes."""

from django.test import SimpleTestCase
from django.urls import resolve


class DiplomesAPITestCase(SimpleTestCase):
    def test_diplome_routes_are_registered(self):
        list_match = resolve("/api/v1/diplomes/")
        detail_match = resolve("/api/v1/diplomes/1/")
        pdf_match = resolve("/api/v1/diplomes/1/pdf_officiel/")
        catalogue_match = resolve("/api/v1/diplomes/catalogue/")

        self.assertEqual(list_match.url_name, "diplome-list")
        self.assertEqual(detail_match.url_name, "diplome-detail")
        self.assertEqual(pdf_match.url_name, "diplome-pdf-officiel")
        self.assertEqual(catalogue_match.url_name, "diplome-catalogue-list")
