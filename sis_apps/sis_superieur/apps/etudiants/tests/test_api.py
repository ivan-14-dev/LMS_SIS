"""API tests for etudiants."""

from django.test import SimpleTestCase
from django.urls import resolve


class EtudiantsAPITestCase(SimpleTestCase):
    def test_individual_subject_routes_are_registered(self):
        list_match = resolve("/api/v1/etudiants/1/matieres-individuelles/")
        remove_match = resolve("/api/v1/etudiants/1/retirer-matiere-individuelle/")

        assert list_match.url_name == "matieres-individuelles"
        assert remove_match.url_name == "retirer-matiere-individuelle"
