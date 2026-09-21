"""API tests for portail_doyen."""

from types import SimpleNamespace

from django.test import SimpleTestCase
from django.urls import resolve
from rest_framework.test import APIRequestFactory

from apps.portail_doyen.api import PortailDoyenViewSet


class PortailDoyenAPITestCase(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def test_tableau_bord_route_is_registered(self):
        match = resolve("/api/v1/portail/doyen/tableau_bord/")

        self.assertEqual(match.url_name, "portail-doyen-tableau-bord")

    def test_budget_route_is_registered(self):
        match = resolve("/api/v1/portail/doyen/budget/")

        self.assertEqual(match.url_name, "portail-doyen-budget")

    def test_tableau_bord_rejects_invalid_faculte_id(self):
        request = self.factory.get("/api/v1/portail/doyen/tableau_bord/?faculte_id=abc")
        request.user = SimpleNamespace()
        view = PortailDoyenViewSet()
        view.request = request

        response = view.tableau_bord(request)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"], "faculte_id invalide.")
