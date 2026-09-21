"""API tests for portail_enseignant."""

from types import SimpleNamespace

from django.test import SimpleTestCase
from django.urls import resolve
from rest_framework.test import APIRequestFactory

from apps.portail_enseignant.api import PortailEnseignantViewSet


class PortailEnseignantAPITestCase(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = SimpleNamespace(enseignant_profile=object())

    def test_tableau_bord_route_is_registered(self):
        match = resolve("/api/v1/portail/staff/tableau_bord/")

        self.assertEqual(match.url_name, "portail-staff-tableau-bord")

    def test_notes_a_saisir_route_is_registered(self):
        match = resolve("/api/v1/portail/staff/notes_a_saisir/")

        self.assertEqual(match.url_name, "portail-staff-notes-a-saisir")

    def test_etudiants_cours_rejects_unassigned_ecue(self):
        request = self.factory.get("/api/v1/portail/enseignant/etudiants_cours/?ecue_id=9")
        request.user = self.user
        view = PortailEnseignantViewSet()
        view.request = request
        view._accessible_ecue_ids = lambda _request: {1, 2}

        response = view.etudiants_cours(request)

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["error"], "ECUE non trouvé ou non autorisé.")

    def test_emploi_du_temps_rejects_invalid_week(self):
        request = self.factory.get("/api/v1/portail/enseignant/emploi_du_temps/?semaine=abc")
        request.user = self.user
        view = PortailEnseignantViewSet()
        view.request = request

        response = view.emploi_du_temps(request)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"], "semaine invalide.")
