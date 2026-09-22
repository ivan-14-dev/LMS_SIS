"""API tests for portail_doyen."""

from types import SimpleNamespace

from apps.portail_doyen.api import PortailDoyenViewSet
from django.test import SimpleTestCase
from django.urls import resolve
from rest_framework.test import APIRequestFactory


class PortailDoyenAPITestCase(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def test_tableau_bord_route_is_registered(self):
        match = resolve("/api/v1/portail/staff/tableau_bord/")

        assert match.url_name == "portail-staff-tableau-bord"

    def test_statistiques_formations_route_is_registered(self):
        match = resolve("/api/v1/portail/staff/statistiques_formations/")

        assert match.url_name == "portail-staff-statistiques-formations"

    def test_tableau_bord_rejects_invalid_faculte_id(self):
        request = self.factory.get("/api/v1/portail/doyen/tableau_bord/?faculte_id=abc")
        request.user = SimpleNamespace()
        request.query_params = request.GET
        view = PortailDoyenViewSet()
        view.request = request

        response = view.tableau_bord(request)

        assert response.status_code == 400
        assert response.data["error"] == "faculte_id invalide."
