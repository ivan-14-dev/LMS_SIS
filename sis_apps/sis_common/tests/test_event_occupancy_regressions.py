"""Real-database regressions for wave38 occupancy review findings."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event
from time import monotonic, sleep
from unittest import skipUnless

from apps.core.models import ModuleConfiguration
from django.apps import apps
from django.conf import settings
from django.contrib.auth.models import Permission
from django.db import connection, connections, transaction
from django.test import TransactionTestCase
from django_tenants.utils import schema_context
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from sis_common.event_occupancy import room_model
from sis_common.tests.test_institutional_events import URL, EventFixture


class EventClockRegressionTests(EventFixture):
    def exam(self, day, start, duration):
        course = self.course()
        if settings.SIS_VARIANT == "secondaire":
            session = apps.get_model("examens", "SessionExamen").objects.create(
                annee_scolaire=course.classe.annee_scolaire, nom="Examen DST", type="controle",
                date_debut=day, date_fin=day,
            )
            fields = {"matiere": course.matiere, "salle_principale": self.room2}
        else:
            session = apps.get_model("examens", "SessionExamen").objects.create(
                semestre=course.semestre, numero=1, date_debut=day, date_fin=day
            )
            fields = {"ecue": course.ecue, "lieu": self.room2.code}
        return apps.get_model("examens", "EpreuveExamen").objects.create(
            session=session, date=day, heure_debut=start, duree_minutes=duration, **fields
        )

    def event_at(self, start, end):
        return {**self.payload, "salle": self.room2.pk, "debut": start, "fin": end}

    def test_spring_exam_blocks_actual_elapsed_duration_and_allows_utc_adjacency(self):
        self.exam("2027-03-28", "01:30", 120)
        before = self.counts()
        response = self.client.post(
            URL, self.event_at("2027-03-28T03:45:00+02:00", "2027-03-28T04:15:00+02:00"), format="json"
        )
        assert response.status_code == 400, response.data
        assert self.counts() == before
        response = self.client.post(
            URL, self.event_at("2027-03-28T04:30:00+02:00", "2027-03-28T05:00:00+02:00"), format="json"
        )
        assert response.status_code == 201, response.data

    def test_spring_exam_cannot_be_added_over_an_existing_event(self):
        response = self.client.post(
            URL, self.event_at("2027-03-28T03:45:00+02:00", "2027-03-28T04:15:00+02:00"), format="json"
        )
        assert response.status_code == 201, response.data
        before = self.counts()
        with self.assertRaises(ValidationError), transaction.atomic():  # noqa: PT027
            self.exam("2027-03-28", "01:30", 120)
        assert apps.get_model("examens", "EpreuveExamen").objects.count() == 0
        assert self.counts() == before

    def test_autumn_exam_does_not_artificially_extend_its_physical_duration(self):
        self.exam("2027-10-31", "01:30", 120)
        response = self.client.post(
            URL, self.event_at("2027-10-31T02:15:00+01:00", "2027-10-31T02:25:00+01:00"), format="json"
        )
        assert response.status_code == 400, response.data
        response = self.client.post(
            URL, self.event_at("2027-10-31T02:30:00+01:00", "2027-10-31T03:00:00+01:00"), format="json"
        )
        assert response.status_code == 201, response.data

    def test_ambiguous_exam_start_checks_both_folds_without_extending_either_duration(self):
        self.exam("2027-10-31", "02:30", 30)
        before = self.counts()
        for offset in ("+02:00", "+01:00"):
            response = self.client.post(
                URL, self.event_at(f"2027-10-31T02:40:00{offset}", f"2027-10-31T02:50:00{offset}"), format="json"
            )
            assert response.status_code == 400, response.data
            assert self.counts() == before
        response = self.client.post(
            URL, self.event_at("2027-10-31T03:00:00+01:00", "2027-10-31T03:15:00+01:00"), format="json"
        )
        assert response.status_code == 201, response.data

    def test_overnight_weekly_course_blocks_the_following_local_day(self):
        course = self.course()
        course.salle = self.room2
        if settings.SIS_VARIANT == "secondaire":
            course.jour, course.heure_debut, course.heure_fin = 7, "23:00", "02:00"
        else:
            course.jour = 6
            slot = course.creneau_horaire
            slot.heure_debut, slot.heure_fin = "23:00", "02:00"
            slot.save()
        course.save()
        before = self.counts()
        response = self.client.post(
            URL, self.event_at("2027-03-08T01:00:00+01:00", "2027-03-08T01:30:00+01:00"), format="json"
        )
        assert response.status_code == 400, response.data
        assert self.counts() == before

    @skipUnless(settings.SIS_VARIANT == "secondaire", "Secondary weekly room constraints")
    def test_overnight_constraint_blocks_next_day_and_allows_exact_end(self):
        apps.get_model("emplois_du_temps", "Contrainte").objects.create(
            salle=self.room2, type="indispo_salle", jour=7, heure_debut="23:00", heure_fin="02:00"
        )
        before = self.counts()
        response = self.client.post(
            URL, self.event_at("2027-03-08T01:00:00+01:00", "2027-03-08T01:30:00+01:00"), format="json"
        )
        assert response.status_code == 400, response.data
        assert self.counts() == before
        response = self.client.post(
            URL, self.event_at("2027-03-08T02:00:00+01:00", "2027-03-08T02:30:00+01:00"), format="json"
        )
        assert response.status_code == 201, response.data

    @skipUnless(settings.SIS_VARIANT == "secondaire", "Secondary weekly room constraints")
    def test_overnight_constraint_creation_is_rejected_atomically_against_next_day_event(self):
        response = self.client.post(
            URL, self.event_at("2027-03-08T01:00:00+01:00", "2027-03-08T01:30:00+01:00"), format="json"
        )
        assert response.status_code == 201, response.data
        self.other.user_permissions.add(Permission.objects.get(
            content_type__app_label="emplois_du_temps", codename="change_creneau"
        ))
        self.client.force_authenticate(self.users.objects.get(pk=self.other.pk))
        before = self.counts()
        response = self.client.post("/api/v1/edt/contraintes/", {
            "salle": self.room2.pk, "type": "indispo_salle", "jour": 7,
            "heure_debut": "23:00", "heure_fin": "02:00",
        }, format="json")
        assert response.status_code == 400, response.data
        assert apps.get_model("emplois_du_temps", "Contrainte").objects.count() == 0
        assert self.counts() == before


class EventLockOrderRegressionTests(EventFixture):
    @classmethod
    def _fixture_setup(cls):
        TransactionTestCase._fixture_setup.__func__(cls)

    def _fixture_teardown(self):
        with schema_context(self.tenant.schema_name):
            TransactionTestCase._fixture_teardown(self)

    def test_http_room_reservation_and_room_update_do_not_deadlock_with_module_disabled(self):
        assert not connection.in_atomic_block
        ModuleConfiguration.objects.filter(etablissement=self.tenant).update(enabled={"sis.events": False})
        if settings.SIS_VARIANT == "superieur":
            self.other.user_permissions.add(Permission.objects.get(
                content_type__app_label="emplois_du_temps", codename="change_creneaucours"
            ))
            reservation = apps.get_model("emplois_du_temps", "Reservation").objects.create(
                salle=self.room, demandeur=self.other, date="2027-03-08",
                heure_debut="10:00", heure_fin="11:00", motif="reunion",
            )
            url, payload, expected = f"/api/v1/edt/reservations/{reservation.pk}/valider/", {"action": "confirmer"}, 200
        else:
            url, payload, expected = "/api/v1/salles/indisponibilites/", {
                "salle": self.room.pk, "date_debut": "2027-03-08", "date_fin": "2027-03-08",
            }, 201
        row_held, release_http, writer_ready = Event(), Event(), Event()
        backend_pids = {}
        room_table = room_model()._meta.db_table

        def reserve():
            paused = False

            def pause_after_real_row_lock(execute, sql, params, many, context):
                nonlocal paused
                result = execute(sql, params, many, context)
                if not paused and room_table in sql and "FOR" in sql and "UPDATE" in sql:
                    paused = True
                    row_held.set()
                    assert release_http.wait(15), "Coordinator never released the actual HTTP row lock."
                return result

            try:
                with schema_context(self.tenant.schema_name):
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT pg_backend_pid()")
                        backend_pids["http"] = cursor.fetchone()[0]
                    client = APIClient(SERVER_NAME=self.get_test_tenant_domain())
                    client.force_authenticate(self.users.objects.get(pk=self.other.pk))
                    with connection.execute_wrapper(pause_after_real_row_lock):
                        response = client.post(url, payload, format="json")
                        assert response.status_code == expected, response.data
            finally:
                connections["default"].close()

        def change_room():
            try:
                assert row_held.wait(15), "HTTP request never acquired its room row lock."
                with schema_context(self.tenant.schema_name):
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT pg_backend_pid()")
                        backend_pids["writer"] = cursor.fetchone()[0]
                    room = room_model().objects.get(pk=self.room.pk)
                    room.capacite = 11
                    writer_ready.set()
                    room.save(update_fields=["capacite"])
            finally:
                connections["default"].close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            first, second = pool.submit(reserve), pool.submit(change_room)
            try:
                assert row_held.wait(15)
                assert writer_ready.wait(15)
                deadline = monotonic() + 15
                blocked = False
                while monotonic() < deadline:
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT pg_blocking_pids(%s)", [backend_pids["writer"]])
                        blocked = backend_pids["http"] in cursor.fetchone()[0]
                    if blocked:
                        break
                    sleep(0.01)
                assert blocked, "Did not observe the competing writer blocked in PostgreSQL."
            finally:
                release_http.set()
            first.result(timeout=20)
            second.result(timeout=20)
        self.room.refresh_from_db()
        assert self.room.capacite == 11
        if settings.SIS_VARIANT == "superieur":
            reservation.refresh_from_db()
            assert reservation.statut == "confirmee"
