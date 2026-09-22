"""API tests for stages."""

from django.test import SimpleTestCase
from django.urls import resolve


class StagesAPITestCase(SimpleTestCase):
    """Vérifie que les ViewSets `stages` sont bien routés (et non des stubs morts)."""

    def test_routes_are_registered(self):
        assert resolve("/api/v1/stages/offres-stage/").url_name == "offre-stage-list"
        assert resolve("/api/v1/stages/candidatures-stage/").url_name == "candidature-stage-list"
        assert resolve("/api/v1/stages/conventions-stage/").url_name == "convention-stage-list"
