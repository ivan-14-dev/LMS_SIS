"""API tests for classes."""

from django.test import SimpleTestCase
from django.urls import resolve


class ClassesAPITestCase(SimpleTestCase):
    def test_class_history_route_is_registered(self):
        history_match = resolve("/api/v1/classes/classes/1/historique/")
        assert history_match.url_name == "classe-historique"
