"""API tests for portail_doyen."""

from types import SimpleNamespace

from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.portail_doyen.api import PortailDoyenViewSet
from apps.structure.models import Departement, Faculte
from apps.utilisateurs.models import Utilisateur
from django.test import SimpleTestCase
from django.urls import resolve
from rest_framework.test import APIRequestFactory, force_authenticate


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


class FaculteScopeTestCase(TenantAPITestCase):
    def test_faculte_filter_rejects_out_of_scope_faculty_and_accepts_own(self):
        dean = Utilisateur.objects.create_user(
            username="dean_scoped", role="doyen", etablissement=self.tenant
        )
        own = Faculte.objects.create(universite=self.tenant, nom="Sciences", code="SCI")
        other = Faculte.objects.create(universite=self.tenant, nom="Arts", code="ART")
        Departement.objects.create(faculte=own, nom="Math", code="MAT")
        Departement.objects.create(faculte=other, nom="History", code="HIS")
        dean.attributs_acces = {
            "permission_scopes": {"formations.view_formation": {"facultes": [own.pk]}}
        }
        dean.save(update_fields=["attributs_acces"])

        def dashboard(faculte_id):
            request = APIRequestFactory().get("/", {"faculte_id": faculte_id})
            request.tenant = self.tenant
            force_authenticate(request, user=dean)
            return PortailDoyenViewSet.as_view({"get": "tableau_bord"})(request)

        response = dashboard(other.pk)
        self.assertEqual(response.status_code, 404)
        response = dashboard(own.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["faculte"]["id"], own.pk)
        self.assertEqual(response.data["statistiques"]["nb_departements"], 1)
