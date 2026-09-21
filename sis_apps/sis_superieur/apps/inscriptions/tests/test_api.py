"""API tests for inscriptions."""

from django.test import SimpleTestCase
from django.urls import resolve


class InscriptionsAPITestCase(SimpleTestCase):
    def test_inscription_routes_are_registered(self):
        list_match = resolve("/api/v1/inscriptions/")
        detail_match = resolve("/api/v1/inscriptions/1/")
        validate_match = resolve("/api/v1/inscriptions/1/valider/")
        refuse_match = resolve("/api/v1/inscriptions/1/refuser/")

        self.assertEqual(list_match.url_name, "inscription-list")
        self.assertEqual(detail_match.url_name, "inscription-detail")
        self.assertEqual(validate_match.url_name, "inscription-valider")
        self.assertEqual(refuse_match.url_name, "inscription-refuser")
