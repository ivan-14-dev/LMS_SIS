"""API tests for entreprises."""

from django.test import SimpleTestCase
from django.urls import resolve


class EntreprisesAPITestCase(SimpleTestCase):
    """Vérifie que les ViewSets `entreprises` sont bien routés (et non des stubs morts)."""

    def test_routes_are_registered(self):
        assert resolve("/api/v1/entreprises/entreprises/").url_name == "entreprise-list"
        assert resolve("/api/v1/entreprises/contacts-entreprises/").url_name == "contact-entreprise-list"
