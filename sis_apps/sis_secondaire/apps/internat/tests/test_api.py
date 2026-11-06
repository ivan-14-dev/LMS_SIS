"""API tests for internat."""

from datetime import timedelta

from apps.eleves.models import Eleve
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.internat.models import BatimentInternat, Chambre, OccupantChambre
from apps.utilisateurs.models import Utilisateur
from django.test import SimpleTestCase
from django.urls import resolve
from django.utils import timezone
from django_tenants.utils import schema_context


class InternatAPITestCase(SimpleTestCase):
    """Vérifie que les ViewSets `internat` sont bien routés (et non des stubs morts)."""

    def test_routes_are_registered(self):
        assert resolve("/api/v1/internat/batiments/").url_name == "batiment-internat-list"
        assert resolve("/api/v1/internat/chambres/").url_name == "chambre-list"
        assert resolve("/api/v1/internat/occupants-chambres/").url_name == "occupant-chambre-list"
        assert resolve("/api/v1/internat/etudes-surveillees/").url_name == "etude-surveillee-list"


class RoomOccupationCapacityTestCase(TenantAPITestCase):
    def setUp(self):
        admin = Utilisateur.objects.create_superuser(
            "internat-admin", role="super_admin", etablissement=self.tenant
        )
        self.client.force_authenticate(admin)
        building = BatimentInternat.objects.create(nom="Bâtiment A")
        self.room = Chambre.objects.create(batiment=building, numero="101", capacite=1)
        self.other_room = Chambre.objects.create(batiment=building, numero="102", capacite=1)
        self.pupils = []
        for number in range(1, 5):
            user = Utilisateur.objects.create_user(
                f"internat-pupil-{number}", role="eleve", etablissement=self.tenant
            )
            self.pupils.append(
                Eleve.objects.create(
                    etablissement=self.tenant,
                    user=user,
                    matricule=f"INTERNAT-{number}",
                    date_naissance="2010-01-01",
                    lieu_naissance="Paris",
                    sexe="F",
                    date_inscription="2026-09-01",
                )
            )
        self.url = "/api/v1/internat/occupants-chambres/"

    def payload(self, pupil, room=None, start="2026-09-01", end=None):
        return {
            "chambre": (room or self.room).pk,
            "eleve": pupil.pk,
            "date_debut": start,
            "date_fin": end,
        }

    def test_create_and_update_respect_capacity_on_inclusive_dates(self):
        first = self.client.post(
            self.url, self.payload(self.pupils[0], end="2026-09-10"), format="json"
        )
        assert first.status_code == 201, first.data

        occupied = self.client.post(
            self.url,
            self.payload(self.pupils[1], start="2026-09-10", end="2026-09-12"),
            format="json",
        )
        assert occupied.status_code == 400, occupied.data
        assert "chambre" in occupied.data

        later = self.client.post(
            self.url,
            self.payload(self.pupils[1], start="2026-09-11", end="2026-09-12"),
            format="json",
        )
        assert later.status_code == 201, later.data
        later_url = f"{self.url}{later.data['id']}/"
        move_date = self.client.patch(later_url, {"date_debut": "2026-09-10"}, format="json")
        assert move_date.status_code == 400, move_date.data
        assert "chambre" in move_date.data
        assert self.client.get(later_url).data["date_debut"] == "2026-09-11"

        first_url = f"{self.url}{first.data['id']}/"
        extend = self.client.patch(first_url, {"date_fin": None}, format="json")
        assert extend.status_code == 400, extend.data
        assert self.client.get(first_url).data["date_fin"] == "2026-09-10"

        in_other_room = self.client.post(
            self.url,
            self.payload(self.pupils[2], room=self.other_room, start="2026-09-02"),
            format="json",
        )
        assert in_other_room.status_code == 201, in_other_room.data
        transfer_url = f"{self.url}{in_other_room.data['id']}/"
        transfer = self.client.patch(transfer_url, {"chambre": self.room.pk}, format="json")
        assert transfer.status_code == 400, transfer.data
        assert self.client.get(transfer_url).data["chambre"] == self.other_room.pk
        assert OccupantChambre.objects.filter(chambre=self.room).count() == 2

    def test_capacity_counts_simultaneous_not_sequential_occupants(self):
        room = Chambre.objects.create(batiment=self.room.batiment, numero="103", capacite=2)
        for pupil, start, end in [
            (self.pupils[0], "2026-09-01", "2026-09-03"),
            (self.pupils[1], "2026-09-05", "2026-09-07"),
        ]:
            response = self.client.post(
                self.url, self.payload(pupil, room=room, start=start, end=end), format="json"
            )
            assert response.status_code == 201, response.data
        spanning = self.client.post(
            self.url,
            self.payload(self.pupils[2], room=room, start="2026-09-01", end="2026-09-07"),
            format="json",
        )
        assert spanning.status_code == 201, spanning.data
        extra = self.client.post(
            self.url,
            self.payload(self.pupils[3], room=room, start="2026-09-04", end="2026-09-05"),
            format="json",
        )
        assert extra.status_code == 400, extra.data
        assert "chambre" in extra.data

    def test_pupil_cannot_occupy_two_rooms_on_overlapping_dates_or_reactivation(self):
        first = self.client.post(
            self.url, self.payload(self.pupils[0], end="2026-09-10"), format="json"
        )
        assert first.status_code == 201, first.data
        first_url = f"{self.url}{first.data['id']}/"

        overlap = self.client.post(
            self.url,
            self.payload(
                self.pupils[0], room=self.other_room, start="2026-09-10", end="2026-09-12"
            ),
            format="json",
        )
        assert overlap.status_code == 400, overlap.data
        assert "eleve" in overlap.data

        later = self.client.post(
            self.url,
            self.payload(
                self.pupils[0], room=self.other_room, start="2026-09-11", end="2026-09-12"
            ),
            format="json",
        )
        assert later.status_code == 201, later.data
        later_url = f"{self.url}{later.data['id']}/"

        overlap = self.client.patch(later_url, {"date_debut": "2026-09-10"}, format="json")
        assert overlap.status_code == 400, overlap.data
        assert "eleve" in overlap.data
        assert self.client.get(later_url).data["date_debut"] == "2026-09-11"

        reopened = self.client.patch(first_url, {"date_fin": None}, format="json")
        assert reopened.status_code == 400, reopened.data
        assert "eleve" in reopened.data
        assert self.client.get(first_url).data["date_fin"] == "2026-09-10"

        unchanged = self.client.patch(first_url, {"motif_fin": "Fin du séjour"}, format="json")
        assert unchanged.status_code == 200, unchanged.data
        assert self.client.delete(later_url).status_code == 204
        reopened = self.client.patch(first_url, {"date_fin": None}, format="json")
        assert reopened.status_code == 200, reopened.data

    def test_room_capacity_cannot_be_reduced_below_existing_occupation(self):
        room = Chambre.objects.create(batiment=self.room.batiment, numero="103", capacite=2)
        today = timezone.localdate()
        for pupil in self.pupils[:2]:
            response = self.client.post(
                self.url,
                self.payload(pupil, room=room, start=str(today), end=str(today + timedelta(days=10))),
                format="json",
            )
            assert response.status_code == 201, response.data
        url = f"/api/v1/internat/chambres/{room.pk}/"
        reduced = self.client.patch(url, {"capacite": 1}, format="json")
        assert reduced.status_code == 400, reduced.data
        assert "capacite" in reduced.data
        assert self.client.get(url).data["capacite"] == 2

    def test_room_capacity_can_be_reduced_after_stays_have_ended(self):
        room = Chambre.objects.create(batiment=self.room.batiment, numero="103", capacite=2)
        end = timezone.localdate() - timedelta(days=1)
        for pupil in self.pupils[:2]:
            response = self.client.post(
                self.url,
                self.payload(pupil, room=room, start=str(end - timedelta(days=2)), end=str(end)),
                format="json",
            )
            assert response.status_code == 201, response.data

        updated = self.client.patch(f"/api/v1/internat/chambres/{room.pk}/", {"capacite": 1}, format="json")
        assert updated.status_code == 200, updated.data
        room.refresh_from_db()
        assert room.capacite == 1

    def test_liberer_does_not_end_future_reservation_or_free_its_capacity(self):
        today = timezone.now().date()
        start = today + timedelta(days=2)
        end = start + timedelta(days=3)
        reserved = self.client.post(
            self.url, self.payload(self.pupils[0], start=str(start)), format="json"
        )
        assert reserved.status_code == 201, reserved.data
        url = f"{self.url}{reserved.data['id']}/liberer/"

        rejected = self.client.post(url, {"motif": "Départ"}, format="json")
        assert rejected.status_code == 400, rejected.data
        reservation = OccupantChambre.objects.get(pk=reserved.data["id"])
        assert reservation.date_debut == start
        assert reservation.date_fin is None
        assert reservation.motif_fin == ""

        conflicting = self.client.post(
            self.url, self.payload(self.pupils[1], start=str(start), end=str(end)),
            format="json",
        )
        assert conflicting.status_code == 400, conflicting.data
        assert "chambre" in conflicting.data

        current = self.client.post(
            self.url,
            self.payload(self.pupils[2], room=self.other_room, start=str(today - timedelta(days=1))),
            format="json",
        )
        assert current.status_code == 201, current.data
        released = self.client.post(
            f"{self.url}{current.data['id']}/liberer/", {"motif": "Départ"}, format="json"
        )
        assert released.status_code == 200, released.data
        active_stay = OccupantChambre.objects.get(pk=current.data["id"])
        assert active_stay.date_fin == today
        assert active_stay.motif_fin == "Départ"

    def test_foreign_tenant_occupancy_is_hidden_and_pupil_cannot_be_assigned(self):
        foreign = type(self.tenant)(schema_name="foreign_internat")
        self.setup_tenant(foreign)
        foreign.auto_create_schema = False
        with schema_context("public"):
            foreign.save()
        user = Utilisateur.objects.create_user(
            "foreign-internat-pupil", role="eleve", etablissement=foreign
        )
        pupil = Eleve.objects.create(
            etablissement=foreign,
            user=user,
            matricule="FOREIGN-INTERNAT",
            date_naissance="2010-01-01",
            lieu_naissance="Paris",
            sexe="F",
            date_inscription="2026-09-01",
        )
        foreign_stay = OccupantChambre.objects.create(
            chambre=self.other_room, eleve=pupil, date_debut="2026-09-01", date_fin="2026-09-10"
        )
        rejected = self.client.post(
            self.url, self.payload(pupil, start="2026-09-11"), format="json"
        )
        assert rejected.status_code == 400, rejected.data
        assert "eleve" in rejected.data

        valid = self.client.post(
            self.url, self.payload(self.pupils[0], start="2026-09-11"), format="json"
        )
        assert valid.status_code == 201, valid.data
        listed = self.client.get(self.url)
        assert listed.status_code == 200, listed.data
        results = (
            listed.data.get("results", listed.data)
            if isinstance(listed.data, dict)
            else listed.data
        )
        assert [stay["id"] for stay in results] == [valid.data["id"]]
        foreign_url = f"{self.url}{foreign_stay.pk}/"
        assert self.client.get(foreign_url).status_code == 404
        assert (
            self.client.patch(foreign_url, {"date_fin": "2026-09-09"}, format="json").status_code
            == 404
        )
        foreign_stay.refresh_from_db()
        assert str(foreign_stay.date_fin) == "2026-09-10"

        detail_url = f"{self.url}{valid.data['id']}/"
        rejected = self.client.patch(detail_url, {"eleve": pupil.pk}, format="json")
        assert rejected.status_code == 400, rejected.data
        assert "eleve" in rejected.data
        assert self.client.get(detail_url).data["eleve"] == self.pupils[0].pk
