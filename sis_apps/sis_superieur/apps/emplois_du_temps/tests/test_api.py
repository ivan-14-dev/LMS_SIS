"""API tests for emplois_du_temps."""

from django.db import connection
from django.test import SimpleTestCase
from django.urls import resolve
from django_tenants.utils import schema_context

from sis_common.tests.test_grade_entry import GradeEntryFixture

from apps.emplois_du_temps.models import CreneauCours
from apps.emplois_du_temps.serializers import CreneauCoursCreateUpdateSerializer


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
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.other_tenant = cls.tenant.__class__(schema_name="edt_group_other")
        cls.setup_tenant(cls.other_tenant)
        with schema_context("public"):
            cls.other_tenant.save(verbosity=0)

    @classmethod
    def tearDownClass(cls):
        connection.set_schema_to_public()
        # La suppression ORM traverse des tables propres au tenant, absentes du schéma public.
        cls.other_tenant._drop_schema(force_drop=True)
        cls.tenant.__class__.objects.filter(pk=cls.other_tenant.pk)._raw_delete(using="default")
        super().tearDownClass()

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

    def test_group_conflicts_on_create_and_update_even_with_different_rooms(self):
        url = "/api/v1/edt/creneaux-cours/"
        building = self.room.batiment
        other_room = self.create(
            "emplois_du_temps.Salle", batiment=building, nom="Autre salle", code="S2", capacite=40
        )
        overlapping = self.create("emplois_du_temps.CreneauHoraire", heure_debut="09:00", heure_fin="10:30")
        first = self.client.post(url, {**self.payload, "groupe": "A"}, format="json")
        assert first.status_code == 201, first.data
        other_payload = {**self.payload, "salle": other_room.pk, "creneau_horaire": overlapping.pk}

        conflict = self.client.post(url, {**other_payload, "groupe": "A"}, format="json")
        assert conflict.status_code == 400, conflict.data
        assert "groupe" in conflict.data
        everyone = self.client.post(url, other_payload, format="json")
        assert everyone.status_code == 400, everyone.data
        assert "groupe" in everyone.data

        different_group = self.client.post(url, {**other_payload, "groupe": "B"}, format="json")
        assert different_group.status_code == 201, different_group.data
        identifier = self.client.get(url, {"salle": other_room.pk}).data["results"][0]["id"]
        for group in ("A", ""):
            response = self.client.patch(f"{url}{identifier}/", {"groupe": group}, format="json")
            assert response.status_code == 400, response.data
            assert "groupe" in response.data
        response = self.client.patch(f"{url}{identifier}/", {"commentaire": "Cours confirmé"}, format="json")
        assert response.status_code == 200, response.data

    def test_group_conflicts_respect_boundaries_and_period(self):
        url = "/api/v1/edt/creneaux-cours/"
        overlapping = self.create("emplois_du_temps.CreneauHoraire", heure_debut="09:00", heure_fin="10:30")
        adjacent = self.create("emplois_du_temps.CreneauHoraire", heure_debut="10:00", heure_fin="11:00")
        first = self.client.post(
            url, {**self.payload, "groupe": "A", "semaine_debut": 2, "semaine_fin": 4, "semaines_paires": True},
            format="json",
        )
        assert first.status_code == 201, first.data
        free = self.client.post(
            url,
            {
                **self.payload,
                "groupe": "A",
                "creneau_horaire": adjacent.pk,
                "semaine_debut": 2,
                "semaine_fin": 4,
                "semaines_paires": True,
            },
            format="json",
        )
        assert free.status_code == 201, free.data
        for index, changes in enumerate(
            (
                {"semaine_debut": 5, "semaine_fin": 6},
                {"semaine_debut": 2, "semaine_fin": 4, "semaines_paires": False},
                {"jour": 1},
                {"groupe": "B"},
            )
        ):
            room = self.create(
                "emplois_du_temps.Salle",
                batiment=self.room.batiment,
                nom=f"Salle {index}",
                code=f"S{index + 3}",
                capacite=40,
            )
            response = self.client.post(
                url, {**self.payload, "salle": room.pk, "creneau_horaire": overlapping.pk, "groupe": "A", **changes},
                format="json",
            )
            assert response.status_code == 201, response.data
        conflict_room = self.create(
            "emplois_du_temps.Salle", batiment=self.room.batiment, nom="Salle conflit", code="S7", capacite=40
        )
        conflict = self.client.post(
            url,
            {
                **self.payload,
                "salle": conflict_room.pk,
                "creneau_horaire": overlapping.pk,
                "groupe": "A",
                "semaine_debut": 4,
                "semaine_fin": 4,
                "semaines_paires": True,
            },
            format="json",
        )
        assert conflict.status_code == 400, conflict.data
        assert "groupe" in conflict.data
        other_semester = self.create(
            "etablissement.Semestre",
            annee_universitaire=self.year,
            numero=2,
            type="pair",
            date_debut=self.year.date_debut,
            date_fin=self.year.date_fin,
        )
        other_ue = self.create(
            "ue_ecue.UE",
            maquette=self.subject.ue.maquette,
            semestre=other_semester,
            code="UE2",
            nom="Autre UE",
            credits_ects=6,
        )
        other_ecue = self.create("ue_ecue.ECUE", ue=other_ue, code="EC2", nom="Autre ECUE", credits_ects=6)
        other_period = self.client.post(
            url,
            {
                **self.payload,
                "semestre": other_semester.pk,
                "ecue": other_ecue.pk,
                "groupe": "A",
            },
            format="json",
        )
        assert other_period.status_code == 201, other_period.data

    def test_group_conflicts_are_isolated_between_tenant_schemas(self):
        url = "/api/v1/edt/creneaux-cours/"
        first = self.client.post(url, {**self.payload, "groupe": "A"}, format="json")
        assert first.status_code == 201, first.data

        with schema_context(self.other_tenant.schema_name):
            year = self.create(
                "etablissement.AnneeUniversitaire", universite=self.other_tenant, **self.year_values
            )
            semester = self.create("etablissement.Semestre", annee_universitaire=year, **self.period_values)
            formation = self.create("formations.Formation", code="F1", nom="Licence", type="licence")
            maquette = self.create("formations.MaquetteFormation", formation=formation, annee_universitaire=year)
            ue = self.create("ue_ecue.UE", maquette=maquette, semestre=semester, code="UE1", nom="UE", credits_ects=6)
            ecue = self.create("ue_ecue.ECUE", ue=ue, code="EC1", nom="ECUE", credits_ects=6)
            building = self.create("emplois_du_temps.Batiment", nom="Campus", code="CAMPUS")
            room = self.create("emplois_du_temps.Salle", batiment=building, nom="Salle", code="S1", capacite=40)
            slot = self.create("emplois_du_temps.CreneauHoraire", heure_debut="08:30", heure_fin="10:00")
            serializer = CreneauCoursCreateUpdateSerializer(data={
                "semestre": semester.pk,
                "formation": formation.pk,
                "ecue": ecue.pk,
                "salle": room.pk,
                "jour": 0,
                "creneau_horaire": slot.pk,
                "groupe": "A",
            })
            assert serializer.is_valid(), serializer.errors
            serializer.save()
            assert CreneauCours.objects.count() == 1
        assert CreneauCours.objects.count() == 1

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
