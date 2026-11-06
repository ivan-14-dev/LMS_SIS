"""API tests for cantine."""

from apps.cantine.models import PresenceCantine
from apps.eleves.models import Eleve
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.utilisateurs.models import Utilisateur
from django.test import SimpleTestCase
from django.urls import resolve


class CantineAPITestCase(SimpleTestCase):
    """Vérifie que les ViewSets `cantine` sont bien routés (et non des stubs morts)."""

    def test_routes_are_registered(self):
        assert resolve("/api/v1/cantine/menus/").url_name == "menu-list"
        assert resolve("/api/v1/cantine/inscriptions-cantine/").url_name == "inscription-cantine-list"
        assert resolve("/api/v1/cantine/presences-cantine/").url_name == "presence-cantine-list"


class CantinePointageTestCase(TenantAPITestCase):
    def setUp(self):
        admin = Utilisateur.objects.create_superuser(
            "cantine-admin", role="super_admin", etablissement=self.tenant
        )
        self.client.force_authenticate(admin)
        pupil = Utilisateur.objects.create_user(
            "cantine-pupil", role="eleve", etablissement=self.tenant
        )
        self.eleve = Eleve.objects.create(
            etablissement=self.tenant,
            user=pupil,
            matricule="CANT-1",
            date_naissance="2010-01-01",
            lieu_naissance="Paris",
            sexe="F",
            date_inscription="2026-09-01",
        )
        response = self.client.post(
            "/api/v1/cantine/menus/",
            {"date": "2026-10-12", "plat": "Repas", "regime": "standard"},
            format="json",
        )
        assert response.status_code == 201, response.data
        self.menu_id = response.data["id"]
        response = self.client.post(
            "/api/v1/cantine/inscriptions-cantine/",
            {"eleve": self.eleve.pk, "date_debut": "2026-10-01", "date_fin": "2026-10-31"},
            format="json",
        )
        assert response.status_code == 201, response.data
        self.inscription_url = f"/api/v1/cantine/inscriptions-cantine/{response.data['id']}/"
        self.presences_url = "/api/v1/cantine/presences-cantine/"

    def test_cancelled_inscription_cannot_be_marked_present_via_single_or_bulk_api(self):
        cancelled = self.client.patch(self.inscription_url, {"actif": False}, format="json")
        assert cancelled.status_code == 200, cancelled.data

        single = self.client.post(
            self.presences_url, {"menu": self.menu_id, "eleve": self.eleve.pk, "present": True},
            format="json",
        )
        assert single.status_code == 400, single.data
        assert "eleve" in single.data

        bulk = self.client.post(
            f"{self.presences_url}pointage_masse/",
            {"menu_id": self.menu_id, "pointages": [{"eleve_id": self.eleve.pk, "present": True}]},
            format="json",
        )
        assert bulk.status_code == 400, bulk.data
        assert not PresenceCantine.objects.filter(menu_id=self.menu_id, eleve=self.eleve).exists()

    def test_cancellation_prevents_reactivating_a_presence_but_allows_marking_absent(self):
        response = self.client.post(
            self.presences_url, {"menu": self.menu_id, "eleve": self.eleve.pk, "present": True},
            format="json",
        )
        assert response.status_code == 201, response.data
        presence_url = f"{self.presences_url}{response.data['id']}/"
        cancelled = self.client.patch(self.inscription_url, {"actif": False}, format="json")
        assert cancelled.status_code == 200, cancelled.data

        absent = self.client.patch(presence_url, {"present": False}, format="json")
        assert absent.status_code == 200, absent.data
        reactivated = self.client.patch(presence_url, {"present": True}, format="json")
        assert reactivated.status_code == 400, reactivated.data
        assert not PresenceCantine.objects.get(pk=response.data["id"]).present

    def test_pointage_rejects_an_inscription_outside_its_dates(self):
        response = self.client.patch(self.inscription_url, {"date_fin": "2026-10-11"}, format="json")
        assert response.status_code == 200, response.data
        single = self.client.post(
            self.presences_url, {"menu": self.menu_id, "eleve": self.eleve.pk, "present": True},
            format="json",
        )
        assert single.status_code == 400, single.data
        assert not PresenceCantine.objects.filter(menu_id=self.menu_id, eleve=self.eleve).exists()
