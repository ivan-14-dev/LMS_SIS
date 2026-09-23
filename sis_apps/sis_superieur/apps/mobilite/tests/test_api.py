"""API tests for mobilite."""

from django.test import SimpleTestCase
from django.urls import resolve


class MobiliteAPITestCase(SimpleTestCase):
    """Vérifie que les ViewSets `mobilite` sont bien routés (et non des stubs morts)."""

    def test_routes_are_registered(self):
        assert resolve("/api/v1/mobilite/programmes-mobilite/").url_name == "programme-mobilite-list"
        assert resolve("/api/v1/mobilite/candidatures-mobilite/").url_name == "candidature-mobilite-list"
        assert resolve("/api/v1/mobilite/accords-etudes/").url_name == "accord-etudes-list"
