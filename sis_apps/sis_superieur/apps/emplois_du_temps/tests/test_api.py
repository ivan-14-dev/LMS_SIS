"""API tests for emplois_du_temps."""

from django.test import SimpleTestCase
from django.urls import resolve

from sis_common.tests.test_grade_entry import GradeEntryFixture


class EmploisDuTempsAPITestCase(SimpleTestCase):
    """Vérifie que les ViewSets `emplois_du_temps` sont bien routés (et non des stubs morts)."""

    def test_routes_are_registered(self):
        assert resolve("/api/v1/edt/batiments/").url_name == "batiment-list"
        assert resolve("/api/v1/edt/salles/").url_name == "salle-list"
        assert resolve("/api/v1/edt/creneaux-horaires/").url_name == "creneau-horaire-list"
        assert resolve("/api/v1/edt/creneaux-cours/").url_name == "creneau-cours-list"
        assert resolve("/api/v1/edt/reservations/").url_name == "reservation-list"
        assert resolve("/api/v1/edt/conflits-horaires/").url_name == "conflit-horaire-list"


class PlanningWorkflowTests(GradeEntryFixture):
    def setUp(self):
        super().setUp()
        building = self.create("emplois_du_temps.Batiment", nom="Campus", code="CAMPUS")
        self.room = self.create("emplois_du_temps.Salle", batiment=building, nom="Salle", code="S1", capacite=40)
        self.slot = self.create("emplois_du_temps.CreneauHoraire", heure_debut="08:30", heure_fin="10:00")
        self.payload = {
            "semestre": self.period.pk,
            "formation": self.formation.pk,
            "ecue": self.subject.pk,
            "salle": self.room.pk,
            "jour": 0,
            "creneau_horaire": self.slot.pk,
        }

    def test_create_and_partial_update_preserve_room_conflicts_and_closed_semester(self):
        url = "/api/v1/edt/creneaux-cours/"
        response = self.client.post(url, self.payload, format="json")
        assert response.status_code == 201, response.data
        second = self.client.post(url, {**self.payload, "jour": 1}, format="json")
        assert second.status_code == 201, second.data
        identifier = self.client.get(url).data["results"][1]["id"]
        response = self.client.patch(f"{url}{identifier}/", {"jour": 0}, format="json")
        assert response.status_code == 400, response.data
        response = self.client.get(
            f"{url}par_formation/", {"formation_id": self.formation.pk, "semestre_id": self.period.pk}
        )
        assert response.status_code == 200
        assert len(response.data["emploi_du_temps"][0]) == 1
        assert response.data["emploi_du_temps"][0][0]["enseignant_nom"] == ""
        assert self.client.post(f"/api/v1/etablissement/semestres/{self.period.pk}/cloturer/").status_code == 200
        assert self.client.post(url, {**self.payload, "jour": 2}, format="json").status_code == 400
        assert self.client.patch(f"{url}{identifier}/", {"jour": 2}, format="json").status_code == 400

    def test_room_conflicts_use_clock_overlap_not_slot_identity(self):
        url = "/api/v1/edt/creneaux-cours/"
        overlapping = self.create("emplois_du_temps.CreneauHoraire", heure_debut="09:00", heure_fin="10:30")
        adjacent = self.create("emplois_du_temps.CreneauHoraire", heure_debut="10:00", heure_fin="11:00")
        first = self.client.post(url, self.payload, format="json")
        assert first.status_code == 201, first.data

        conflict = self.client.post(url, {**self.payload, "creneau_horaire": overlapping.pk}, format="json")
        assert conflict.status_code == 400, conflict.data
        assert "salle" in conflict.data

        other_day = self.client.post(
            url, {**self.payload, "jour": 1, "creneau_horaire": overlapping.pk}, format="json"
        )
        assert other_day.status_code == 201, other_day.data
        identifier = self.client.get(url, {"jour": 1}).data["results"][0]["id"]
        moved = self.client.patch(f"{url}{identifier}/", {"jour": 0}, format="json")
        assert moved.status_code == 400, moved.data
        assert "salle" in moved.data

        free = self.client.post(url, {**self.payload, "creneau_horaire": adjacent.pk}, format="json")
        assert free.status_code == 201, free.data

    def test_reservation_confirmation_rechecks_conflicts_and_captures_actor(self):
        url = "/api/v1/edt/reservations/"
        payload = {
            "salle": self.room.pk,
            "date": self.today.isoformat(),
            "heure_debut": "14:00",
            "heure_fin": "15:00",
            "motif": "reunion",
        }
        self.client.force_authenticate(self.teacher)
        assert self.client.post(url, payload, format="json").status_code == 201
        assert self.client.post(url, payload, format="json").status_code == 201
        rows = self.client.get(url).data["results"]
        first, second = (row["id"] for row in rows)
        assert self.client.post(f"{url}{first}/valider/", {"action": "confirmer"}, format="json").status_code == 403
        self.client.force_authenticate(self.admin)
        response = self.client.post(f"{url}{first}/valider/", {"action": "confirmer"}, format="json")
        assert response.status_code == 200, response.data
        assert response.data["demandeur"] == self.teacher.pk
        assert response.data["valide_par"] == self.admin.pk
        assert self.client.post(f"{url}{second}/valider/", {"action": "confirmer"}, format="json").status_code == 400
        assert self.client.post(url, payload, format="json").status_code == 400
