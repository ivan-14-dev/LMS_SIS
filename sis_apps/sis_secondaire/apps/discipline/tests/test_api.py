"""API tests for discipline."""

from django.test import SimpleTestCase
from django.urls import resolve


class DisciplineAPITestCase(SimpleTestCase):
    """Vérifie que les ViewSets `discipline` sont bien routés (et non des stubs morts)."""

    def test_routes_are_registered(self):
        assert resolve("/api/v1/discipline/incidents/").url_name == "incident-list"
        assert resolve("/api/v1/discipline/sanctions/").url_name == "sanction-list"
        assert resolve("/api/v1/discipline/conseils-discipline/").url_name == "conseil-discipline-list"
