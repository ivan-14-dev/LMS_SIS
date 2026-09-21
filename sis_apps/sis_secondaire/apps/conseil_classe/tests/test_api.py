"""API tests for conseil_classe."""

from django.test import SimpleTestCase
from django.urls import resolve


class ConseilClasseAPITestCase(SimpleTestCase):
    def test_conseil_routes_are_exposed(self):
        self.assertEqual(
            resolve("/api/v1/conseils/conseils-classe/").url_name,
            "conseil-classe-list",
        )
        self.assertEqual(
            resolve("/api/v1/conseils/conseils-classe/1/historique/").url_name,
            "conseil-classe-historique",
        )
