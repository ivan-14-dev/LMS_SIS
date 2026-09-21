"""API tests for ue_ecue."""

from django.test import SimpleTestCase
from django.urls import resolve


class UeEcueAPITestCase(SimpleTestCase):
    def test_ue_ecue_history_routes_are_registered(self):
        ue_history = resolve("/api/v1/ue-ecue/ues/1/historique/")
        ecue_history = resolve("/api/v1/ue-ecue/ecues/1/historique/")
        prerequis_history = resolve("/api/v1/ue-ecue/prerequis/1/historique/")

        self.assertEqual(ue_history.url_name, "ue-historique")
        self.assertEqual(ecue_history.url_name, "ecue-historique")
        self.assertEqual(prerequis_history.url_name, "prerequis-historique")
