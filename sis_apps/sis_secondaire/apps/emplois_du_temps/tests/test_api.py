"""API tests for emplois_du_temps."""

from django.test import SimpleTestCase
from django.urls import resolve


class EmploisDuTempsAPITestCase(SimpleTestCase):
    """Vérifie que les ViewSets `emplois_du_temps` sont bien routés (et non des stubs morts)."""

    def test_routes_are_registered(self):
        assert resolve("/api/v1/edt/creneaux/").url_name == "creneau-list"
        assert resolve("/api/v1/edt/contraintes/").url_name == "contrainte-list"
