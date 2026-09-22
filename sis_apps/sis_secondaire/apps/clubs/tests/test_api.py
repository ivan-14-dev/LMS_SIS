"""API tests for clubs."""

from django.test import SimpleTestCase
from django.urls import resolve


class ClubsAPITestCase(SimpleTestCase):
    """Vérifie que les ViewSets `clubs` sont bien routés (et non des stubs morts)."""

    def test_routes_are_registered(self):
        assert resolve("/api/v1/clubs/clubs/").url_name == "club-list"
        assert resolve("/api/v1/clubs/membres-clubs/").url_name == "membre-club-list"
        assert resolve("/api/v1/clubs/activites-clubs/").url_name == "seance-club-list"
