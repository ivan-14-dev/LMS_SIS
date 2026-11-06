"""API tests for salles."""

from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.salles.models import Equipement, Salle
from apps.utilisateurs.models import Utilisateur
from django.test import SimpleTestCase
from django.urls import resolve
from django_tenants.utils import schema_context


class SallesAPITestCase(SimpleTestCase):
    """Vérifie que le ViewSet `salles` est bien routé (et non un stub mort)."""

    def test_routes_are_registered(self):
        assert resolve("/api/v1/salles/").url_name == "salle-list"
        assert resolve("/api/v1/salles/equipements/").url_name == "equipement-list"
        assert resolve("/api/v1/salles/equipements/1/").url_name == "equipement-detail"


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


class EquipementAPITestCase(TenantAPITestCase):
    url = "/api/v1/salles/equipements/"

    def setUp(self):
        admin = Utilisateur.objects.create_superuser(
            "equipements-admin", etablissement=self.tenant
        )
        self.client.force_authenticate(admin)
        self.room = Salle.objects.create(
            etablissement=self.tenant, code="EQ-1", nom="Salle A", capacite=1
        )
        self.other_room = Salle.objects.create(
            etablissement=self.tenant, code="EQ-2", nom="Salle B", capacite=30
        )

    def test_register_assign_move_unassign_and_list(self):
        created = self.client.post(
            self.url, {"identifiant": "INV-001", "nom": "Vidéoprojecteur"}, format="json"
        )
        assert created.status_code == 201, created.data
        assert created.data["etablissement"] == self.tenant.pk
        assert created.data["salle"] is None
        detail_url = f"{self.url}{created.data['id']}/"

        duplicate = self.client.post(
            self.url, {"identifiant": "INV-001", "nom": "Autre appareil"}, format="json"
        )
        assert duplicate.status_code == 400, duplicate.data
        assert "identifiant" in duplicate.data
        other = self.client.post(
            self.url, {"identifiant": "INV-002", "nom": "Écran"}, format="json"
        )
        assert other.status_code == 201, other.data
        duplicate_update = self.client.patch(
            f"{self.url}{other.data['id']}/", {"identifiant": "INV-001"}, format="json"
        )
        assert duplicate_update.status_code == 400, duplicate_update.data
        assert "identifiant" in duplicate_update.data

        for room in (self.room, self.other_room):
            assigned = self.client.patch(detail_url, {"salle": room.pk}, format="json")
            assert assigned.status_code == 200, assigned.data
            assert assigned.data["salle"] == room.pk
            assert assigned.data["salle_nom"] == room.nom
            assert self.client.get(detail_url).data["salle"] == room.pk

        listing = self.client.get(self.url, {"salle": self.other_room.pk})
        assert listing.status_code == 200, listing.data
        results = listing.data.get("results", listing.data)
        assert [item["identifiant"] for item in results] == ["INV-001"]
        assert self.client.get(f"{self.url}{other.data['id']}/").data["identifiant"] == "INV-002"
        assert self.client.patch(detail_url, {"salle": None}, format="json").status_code == 200
        assert self.client.get(detail_url).data["salle"] is None
        assert self.client.get(f"/api/v1/salles/{self.room.pk}/").data["capacite"] == 1

    def test_foreign_establishment_and_room_are_rejected_and_hidden(self):
        foreign = type(self.tenant)(schema_name="foreign_equipment")
        self.setup_tenant(foreign)
        foreign.auto_create_schema = False
        with schema_context("public"):
            foreign.save()
        foreign_room = Salle.objects.create(
            etablissement=foreign, code="FOREIGN", nom="Hors établissement"
        )
        foreign_asset = Equipement.objects.create(
            etablissement=foreign, identifiant="INV-001", nom="Non visible", salle=foreign_room
        )
        invalid_room = self.client.post(
            self.url, {"identifiant": "INV-003", "nom": "Invalide", "salle": 99999999},
            format="json",
        )
        assert invalid_room.status_code == 400, invalid_room.data
        assert "salle" in invalid_room.data

        created = self.client.post(
            self.url,
            {"identifiant": "INV-001", "nom": "Appareil local", "salle": self.room.pk},
            format="json",
        )
        assert created.status_code == 201, created.data
        detail_url = f"{self.url}{created.data['id']}/"
        for payload in (
            {"salle": foreign_room.pk},
            {"etablissement": foreign.pk},
        ):
            rejected = self.client.post(
                self.url, {"identifiant": "INV-002", "nom": "Autre", **payload}, format="json"
            )
            assert rejected.status_code == 400, rejected.data
            rejected = self.client.patch(detail_url, payload, format="json")
            assert rejected.status_code == 400, rejected.data
        assert self.client.get(detail_url).data["salle"] == self.room.pk
        assert self.client.get(f"{self.url}{foreign_asset.pk}/").status_code == 404
        listing = self.client.get(self.url)
        results = listing.data.get("results", listing.data)
        assert [item["id"] for item in results] == [created.data["id"]]
