"""API tests for inscriptions."""

from django.test import SimpleTestCase
from django.urls import resolve


class InscriptionsAPITestCase(SimpleTestCase):
    def test_inscription_routes_are_registered(self):
        list_match = resolve("/api/v1/inscriptions/")
        detail_match = resolve("/api/v1/inscriptions/1/")
        validate_match = resolve("/api/v1/inscriptions/1/valider/")
        refuse_match = resolve("/api/v1/inscriptions/1/refuser/")
        history_match = resolve("/api/v1/inscriptions/1/historique/")

        assert list_match.url_name == "inscription-list"
        assert detail_match.url_name == "inscription-detail"
        assert validate_match.url_name == "inscription-valider"
        assert refuse_match.url_name == "inscription-refuser"
        assert history_match.url_name == "inscription-historique"
