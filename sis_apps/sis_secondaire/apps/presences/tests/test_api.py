"""API tests for presences."""

from django.test import SimpleTestCase
from django.urls import resolve


class PresencesAPITestCase(SimpleTestCase):
    """Vérifie que les ViewSets `presences` sont bien routés (et non des stubs morts)."""

    def test_routes_are_registered(self):
        assert resolve("/api/v1/presences/appels/").url_name == "appel-list"
        assert resolve("/api/v1/presences/presences/").url_name == "presence-list"
        assert resolve("/api/v1/presences/justificatifs/").url_name == "justificatif-list"
