"""API tests for emplois_du_temps."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, local
from unittest.mock import patch

from django.apps import apps
from django.db import connection
from django.test import SimpleTestCase, TransactionTestCase, override_settings
from django.urls import resolve
from django_tenants.utils import get_tenant_domain_model, get_tenant_model, schema_context
from rest_framework.test import APIClient

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


@override_settings(ALLOWED_HOSTS=["testserver", "edt-lock.test.com"])
class ConcurrentPlanningTests(TransactionTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with schema_context("public"):
            cls.tenant = get_tenant_model().objects.create(
                schema_name="edt_lock_test",
                nom="Université de test",
                type="universite_publique",
                adresse="1 rue des Tests",
                code_postal="75000",
                ville="Paris",
                telephone="0100000000",
                email="edt-lock@test.example",
            )
            get_tenant_domain_model().objects.create(
                tenant=cls.tenant, domain="edt-lock.test.com", is_primary=True
            )

    @classmethod
    def tearDownClass(cls):
        connection.set_schema_to_public()
        cls.tenant._drop_schema(force_drop=True)
        apps.get_model("etablissement.Semestre").objects.filter(pk=cls.semestre_pk)._raw_delete(using="default")
        apps.get_model("etablissement.AnneeUniversitaire").objects.filter(pk=cls.year_pk)._raw_delete(using="default")
        get_tenant_domain_model().objects.filter(tenant=cls.tenant).delete()
        get_tenant_model().objects.filter(pk=cls.tenant.pk)._raw_delete(using="default")
        super().tearDownClass()

    def setUp(self):
        connection.set_tenant(self.tenant)

        def create(model, **values):
            return apps.get_model(model).objects.create(**values)

        admin = apps.get_model("utilisateurs.Utilisateur").objects.create_superuser(
            "edt-lock-admin", role="super_admin", etablissement=self.tenant
        )
        self.admin = admin
        year = create(
            "etablissement.AnneeUniversitaire",
            universite=self.tenant,
            libelle="2026",
            date_debut="2026-01-01",
            date_fin="2026-12-31",
        )
        self.__class__.year_pk = year.pk
        semestre = create(
            "etablissement.Semestre",
            annee_universitaire=year,
            numero=1,
            type="impair",
            date_debut=year.date_debut,
            date_fin=year.date_fin,
        )
        self.__class__.semestre_pk = semestre.pk
        formation = create("formations.Formation", code="EDT", nom="Licence", type="licence")
        maquette = create("formations.MaquetteFormation", formation=formation, annee_universitaire=year)
        ue = create("ue_ecue.UE", maquette=maquette, semestre=semestre, code="UE1", nom="UE", credits_ects=6)
        ecue = create("ue_ecue.ECUE", ue=ue, code="EC1", nom="ECUE", credits_ects=6)
        building = create("emplois_du_temps.Batiment", nom="Campus", code="CAMPUS")
        self.rooms = [
            create("emplois_du_temps.Salle", batiment=building, nom=f"Salle {i}", code=f"S{i}", capacite=40)
            for i in range(1, 3)
        ]
        first = create("emplois_du_temps.CreneauHoraire", heure_debut="08:30", heure_fin="10:00")
        overlapping = create("emplois_du_temps.CreneauHoraire", heure_debut="09:00", heure_fin="10:30")
        adjacent = create("emplois_du_temps.CreneauHoraire", heure_debut="10:00", heure_fin="11:00")
        self.slots = first, overlapping, adjacent
        self.payload = {
            "semestre": semestre.pk,
            "formation": formation.pk,
            "ecue": ecue.pk,
            "jour": 0,
        }

    def _concurrent_posts(self, first, second):
        barrier = Barrier(2)
        validated = local()
        original_validate = CreneauCoursCreateUpdateSerializer.validate

        def synchronized_validate(serializer, attrs):
            result = original_validate(serializer, attrs)
            if not getattr(validated, "passed", False):
                validated.passed = True
                barrier.wait(timeout=15)
            return result

        def submit(payload):
            try:
                client = APIClient(SERVER_NAME="edt-lock.test.com")
                client.force_authenticate(self.admin)
                response = client.post("/api/v1/edt/creneaux-cours/", payload, format="json")
                return response.status_code, response.data
            finally:
                connection.close()

        with patch.object(CreneauCoursCreateUpdateSerializer, "validate", synchronized_validate):
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = [executor.submit(submit, payload) for payload in (first, second)]
                return [future.result(timeout=30) for future in futures]

    def test_simultaneous_group_overlap_is_refused_but_independent_or_adjacent_courses_succeed(self):
        first = {**self.payload, "salle": self.rooms[0].pk, "creneau_horaire": self.slots[0].pk, "groupe": "A"}
        overlapping = {**self.payload, "salle": self.rooms[1].pk, "creneau_horaire": self.slots[1].pk}

        responses = self._concurrent_posts(first, {**overlapping, "groupe": "A"})
        assert sorted(status for status, _ in responses) == [201, 400], responses
        assert "groupe" in next(data for status, data in responses if status == 400)
        assert CreneauCours.objects.count() == 1

        CreneauCours.objects.all().delete()
        responses = self._concurrent_posts(first, {**overlapping, "groupe": "B"})
        assert [status for status, _ in responses] == [201, 201], responses

        CreneauCours.objects.all().delete()
        adjacent = {**first, "creneau_horaire": self.slots[2].pk}
        responses = self._concurrent_posts(first, adjacent)
        assert [status for status, _ in responses] == [201, 201], responses


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
