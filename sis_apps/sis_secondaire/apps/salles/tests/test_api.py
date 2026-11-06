"""API tests for salles."""

from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.salles.models import Salle
from apps.utilisateurs.models import Utilisateur
from django.test import SimpleTestCase
from django.urls import resolve


class SallesAPITestCase(SimpleTestCase):
    """Vérifie que le ViewSet `salles` est bien routé (et non un stub mort)."""

    def test_routes_are_registered(self):
        assert resolve("/api/v1/salles/").url_name == "salle-list"


class SalleCapacityAPITestCase(TenantAPITestCase):
    def test_room_capacity_must_be_positive_on_create_and_update(self):
        admin = Utilisateur.objects.create_superuser(
            "salles-admin", etablissement=self.tenant
        )
        self.client.force_authenticate(admin)
        url = "/api/v1/salles/"

        rejected = self.client.post(
            url, {"code": "S0", "nom": "Salle vide", "capacite": 0}, format="json"
        )
        assert rejected.status_code == 400, rejected.data
        assert "capacite" in rejected.data
        assert not Salle.objects.filter(code="S0").exists()

        room = self.client.post(
            url, {"code": "S1", "nom": "Salle valide", "capacite": 1}, format="json"
        )
        assert room.status_code == 201, room.data
        room_url = f"{url}{room.data['id']}/"
        rejected = self.client.patch(room_url, {"capacite": 0}, format="json")
        assert rejected.status_code == 400, rejected.data
        assert "capacite" in rejected.data
        assert self.client.get(room_url).data["capacite"] == 1
