"""API tests for emplois_du_temps."""

from django.test import SimpleTestCase
from django.urls import resolve


class EmploisDuTempsAPITestCase(SimpleTestCase):
    """Vérifie que les ViewSets `emplois_du_temps` sont bien routés (et non des stubs morts)."""

    def test_routes_are_registered(self):
        assert resolve("/api/v1/edt/batiments/").url_name == "batiment-list"
        assert resolve("/api/v1/edt/salles/").url_name == "salle-list"
        assert resolve("/api/v1/edt/creneaux-horaires/").url_name == "creneau-horaire-list"
        assert resolve("/api/v1/edt/creneaux-cours/").url_name == "creneau-cours-list"
        assert resolve("/api/v1/edt/reservations/").url_name == "reservation-list"
        assert resolve("/api/v1/edt/conflits-horaires/").url_name == "conflit-horaire-list"
