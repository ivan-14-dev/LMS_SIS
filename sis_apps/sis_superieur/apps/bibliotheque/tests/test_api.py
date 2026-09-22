"""API tests for bibliotheque."""

from django.test import SimpleTestCase
from django.urls import resolve


class BibliothequeAPITestCase(SimpleTestCase):
    """Vérifie que les ViewSets `bibliotheque` sont bien routés (et non des stubs morts)."""

    def test_routes_are_registered(self):
        assert resolve("/api/v1/bibliotheque/livres/").url_name == "livre-list"
        assert resolve("/api/v1/bibliotheque/exemplaires/").url_name == "exemplaire-list"
        assert resolve("/api/v1/bibliotheque/emprunts/").url_name == "emprunt-list"
        assert (
            resolve("/api/v1/bibliotheque/reservations-bibliotheque/").url_name
            == "reservation-bibliotheque-list"
        )
