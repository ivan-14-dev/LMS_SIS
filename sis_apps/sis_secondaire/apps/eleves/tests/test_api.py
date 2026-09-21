"""API tests for eleves."""

from django.test import SimpleTestCase
from django.urls import resolve


class ElevesAPITestCase(SimpleTestCase):
    def test_individual_subject_routes_are_registered(self):
        list_match = resolve("/api/v1/eleves/1/matieres-individuelles/")
        remove_match = resolve("/api/v1/eleves/1/retirer-matiere-individuelle/")

        assert list_match.url_name == "matieres-individuelles"
        assert remove_match.url_name == "retirer-matiere-individuelle"
