import json
import logging
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import timedelta
from queue import Queue
from threading import Event
from time import monotonic, sleep
from unittest.mock import patch

import pytest
from apps.notes.api import NotesViewSet
from django.apps import apps
from django.db import OperationalError, connection, connections, transaction
from django.test import TransactionTestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from django_tenants.utils import schema_context
from rest_framework.exceptions import ValidationError

from sis_common.academic_lifecycle import ensure_academic_open
from sis_common.tests.test_grade_entry import GradeEntryFixture


class AcademicCalendarConcurrencyTests(GradeEntryFixture):
    @classmethod
    def _fixture_setup(cls):
        TransactionTestCase._fixture_setup.__func__(cls)

    def _fixture_teardown(self):
        with schema_context(self.tenant.schema_name):
            TransactionTestCase._fixture_teardown(self)
            # Shared calendars are outside the tenant-schema flush.
            for record in self.shared_fixture_records:
                record.delete()

    def setUp(self):
        self.shared_fixture_records = []
        super().setUp()
        self.shared_fixture_records = [self.year]
        if self.secondary:
            self.shared_fixture_records.append(self.classe.niveau)
        assert not connection.in_atomic_block

    @staticmethod
    def closed_field(record):
        return "cloturee" if hasattr(record, "cloturee") else "cloture"

    @contextmanager
    def hold_calendars(self, records, *, close=False):
        locked, release = Event(), Event()

        def hold():
            try:
                with schema_context(self.tenant.schema_name), transaction.atomic():
                    for record in records:
                        if close:
                            type(record).objects.filter(pk=record.pk).update(**{self.closed_field(record): True})
                        else:
                            ensure_academic_open(record, paths=("",))
                    locked.set()
                    if not release.wait(timeout=15):
                        raise TimeoutError("The test did not release its calendar transaction")
            finally:
                connections["default"].close()

        with ThreadPoolExecutor(max_workers=1) as pool:
            running = pool.submit(hold)
            try:
                assert locked.wait(timeout=10), "The calendar transaction did not acquire its locks"
                yield
            finally:
                release.set()
            running.result(timeout=10)

    def test_independent_guards_share_the_year_and_period(self):
        with self.hold_calendars((self.year, self.period)), transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("SET LOCAL lock_timeout = '200ms'")
            for record in (self.year, self.period):
                ensure_academic_open(record, paths=("",))

    def test_guard_prevents_closure_until_its_transaction_finishes(self):
        def close(record):
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute("SET LOCAL lock_timeout = '200ms'")
                type(record).objects.filter(pk=record.pk).update(**{self.closed_field(record): True})

        with self.hold_calendars((self.year, self.period)):
            for record in (self.year, self.period):
                with self.subTest(calendar=record._meta.label_lower):
                    with pytest.raises(OperationalError) as raised:
                        close(record)
                    assert raised.value.__cause__.diag.sqlstate == "55P03"
                    record.refresh_from_db()
                    assert not getattr(record, self.closed_field(record))

    def test_waiting_guard_rejects_a_concurrently_closed_calendar(self):
        def guard(record, started):
            try:
                with schema_context(self.tenant.schema_name), transaction.atomic():
                    with connection.cursor() as cursor:
                        cursor.execute("SET LOCAL lock_timeout = '10s'")
                        cursor.execute("SELECT pg_backend_pid()")
                        started.put(cursor.fetchone()[0])
                    ensure_academic_open(record, paths=("",))
            finally:
                connections["default"].close()

        for record in (self.year, self.period):
            with self.subTest(calendar=record._meta.label_lower), ThreadPoolExecutor(max_workers=1) as pool:
                started = Queue()
                with self.hold_calendars((record,), close=True):
                    running = pool.submit(guard, record, started)
                    pid = started.get(timeout=10)
                    deadline = monotonic() + 5
                    while True:
                        with connection.cursor() as cursor:
                            cursor.execute("SELECT cardinality(pg_blocking_pids(%s)) > 0", [pid])
                            blocked = cursor.fetchone()[0]
                        if blocked:
                            break
                        assert not running.done(), "The guard proceeded before closure committed"
                        assert monotonic() < deadline, "The guard never waited for the calendar lock"
                        sleep(0.02)
                assert not getattr(record, self.closed_field(record))
                with pytest.raises(ValidationError) as raised:
                    running.result(timeout=10)
                assert "calendrier" in raised.value.detail

    def change_evaluation_concurrently(self, **changes):
        def change():
            try:
                with schema_context(self.tenant.schema_name), transaction.atomic():
                    with connection.cursor() as cursor:
                        cursor.execute("SET LOCAL lock_timeout = '2s'")
                    assert type(self.evaluation).objects.filter(pk=self.evaluation.pk).update(**changes) == 1
            finally:
                connections["default"].close()

        with ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(change).result(timeout=5)

    def test_grade_patch_rechecks_assignment_after_locking_the_note(self):
        assert self.save_grades([self.row(self.learners[0])]).status_code == 200
        note = self.evaluation.notes.get()
        replacement_user = type(self.teacher).objects.create_user(
            "grade-replacement", role="enseignant", etablissement=self.tenant
        )
        replacement = (
            self.create("enseignants.Personnel", user=replacement_user, matricule="ENS-02", date_embauche=self.today)
            if self.secondary
            else replacement_user
        )
        original_update = NotesViewSet.perform_update

        def reassign_then_update(view, serializer):
            self.change_evaluation_concurrently(enseignant_id=replacement.pk)
            return original_update(view, serializer)

        self.client.force_authenticate(self.teacher)
        with patch.object(NotesViewSet, "perform_update", reassign_then_update):
            response = self.client.patch(f"/api/v1/notes/notes/{note.pk}/", {"valeur": "16"}, format="json")
        assert response.status_code == 404, response.data
        note.refresh_from_db()
        self.evaluation.refresh_from_db()
        assert note.valeur == 14
        assert self.evaluation.enseignant_id == replacement.pk

    def test_grade_patch_refreshes_the_window_after_its_second_scope_check(self):
        assert self.save_grades([self.row(self.learners[0])]).status_code == 200
        note = self.evaluation.notes.get()
        checks = []
        original_check = NotesViewSet.check_object_permissions
        closed_at = timezone.now() - timedelta(minutes=1)

        def close_window_after_check(view, request, obj):
            original_check(view, request, obj)
            checks.append(obj.pk)
            if len(checks) == 2:
                self.change_evaluation_concurrently(fin_soumission=closed_at)

        self.client.force_authenticate(self.teacher)
        with patch.object(NotesViewSet, "check_object_permissions", close_window_after_check):
            response = self.client.patch(f"/api/v1/notes/notes/{note.pk}/", {"valeur": "16"}, format="json")
        assert checks == [note.pk, note.pk]
        assert response.status_code == 400, response.data
        assert "soumission" in response.data
        note.refresh_from_db()
        self.evaluation.refresh_from_db()
        assert note.valeur == 14
        assert self.evaluation.fin_soumission == closed_at


class AcademicPeriodCatalogTests(GradeEntryFixture):
    def configure_period_types(self, items):
        original = self.tenant.configuration_academique

        def restore():
            self.tenant.configuration_academique = original
            self.tenant.save(update_fields=["configuration_academique"])

        self.addCleanup(restore)
        self.tenant.configuration_academique = {
            **original,
            "catalogs": {**original.get("catalogs", {}), "period_types": items},
        }
        self.tenant.save(update_fields=["configuration_academique"])

    @property
    def calendar_url(self):
        resource = "periodes" if self.secondary else "semestres"
        return f"/api/v1/etablissement/{resource}/"

    def test_configured_period_type_can_be_created_and_read_through_both_routes(self):
        options = [{"code": "session_courte", "label": "Session courte"}]
        self.configure_period_types([{**options[0], "administrative_note": "Not published to readers"}])
        self.client.force_authenticate(self.teacher)
        response = self.client.get(f"{self.calendar_url}types/")
        assert response.status_code == 200, response.data
        assert response.data == options
        payload = {
            **self.period_values,
            self.year_field: self.year.pk,
            "numero": 2,
            "type": "session_courte",
        }
        assert self.client.post(self.calendar_url, payload, format="json").status_code == 403
        self.client.force_authenticate(self.admin)
        response = self.client.post(self.calendar_url, payload, format="json")
        assert response.status_code == 201, response.data
        created = response.data
        assert created["type"] == "session_courte"
        assert created["type_display"] == "Session courte"
        listing = self.client.get(self.calendar_url)
        assert listing.status_code == 200, listing.data
        assert next(row for row in listing.data["results"] if row["id"] == created["id"])["type_display"] == (
            "Session courte"
        )
        resource = "periodes" if self.secondary else "semestres"
        nested = self.client.get(f"/api/v1/etablissement/annees/{self.year.pk}/{resource}/")
        assert nested.status_code == 200, nested.data
        assert next(row for row in nested.data if row["id"] == created["id"])["type_display"] == "Session courte"

    def test_replacing_catalog_preserves_existing_periods_and_their_date_guards(self):
        self.configure_period_types([{"code": self.period.type, "label": "Ancienne session"}])
        url = f"{self.calendar_url}{self.period.pk}/"
        assert self.client.get(url).data["type_display"] == "Ancienne session"
        self.configure_period_types([{"code": "session_courte", "label": "Session courte"}])
        response = self.client.patch(url, {"date_fin": self.period.date_fin.isoformat()}, format="json")
        assert response.status_code == 200, response.data
        assert response.data["type"] == self.period.type
        assert response.data["type_display"] == self.period.type
        invalid = {"date_fin": (self.year.date_fin + timedelta(days=1)).isoformat()}
        assert self.client.patch(url, invalid, format="json").status_code == 400
        self.period.refresh_from_db()
        assert self.period.date_fin == self.year.date_fin
        assert self.client.post(f"{url}cloturer/", {}, format="json").status_code == 200
        assert self.client.patch(url, {"type": "session_courte"}, format="json").status_code == 400
        self.period.refresh_from_db()
        assert self.period.type == self.period_values["type"]

    def test_empty_catalog_restores_historical_choices_without_opening_anonymous_access(self):
        self.configure_period_types([])
        response = self.client.get(f"{self.calendar_url}types/")
        assert response.status_code == 200, response.data
        expected = [{"code": code, "label": label} for code, label in type(self.period).TYPE_CHOICES]
        assert response.data == expected
        self.client.force_authenticate(None)
        assert self.client.get(f"{self.calendar_url}types/").status_code in (401, 403)


class AcademicLifecycleTests(GradeEntryFixture):
    def test_grade_patch_reads_the_locked_note_once(self):
        assert self.save_grades([self.row(self.learners[0])]).status_code == 200
        note = self.evaluation.notes.get()
        locked_reads = []
        for user in (self.teacher, self.admin):
            self.client.force_authenticate(user)
            with CaptureQueriesContext(connection) as queries:
                response = self.client.patch(
                    f"/api/v1/notes/notes/{note.pk}/", {"valeur": "16", "appreciation": "Révision"}, format="json"
                )
            assert response.status_code == 200, response.data
            assert response.data["valeur"] == "16.00"
            note.refresh_from_db()
            assert note.valeur == 16
            assert note.appreciation == "Révision"
            assert note.evaluation_id == self.evaluation.pk
            locked_reads.append(
                sum(
                    f'FROM "{self.note_model._meta.db_table}"' in query["sql"] and "FOR UPDATE" in query["sql"]
                    for query in queries.captured_queries
                )
            )
        assert locked_reads == [1, 1], f"Repeated locked note reads for teacher/admin: {locked_reads}"

    def exam_result(self):
        data = {"date_debut": self.today.isoformat(), "date_fin": self.today.isoformat()}
        data.update(
            {"annee_scolaire": self.year.pk, "type": "examen_blanc", "nom": "Examen"}
            if self.secondary
            else {"semestre": self.period.pk, "numero": 1, "type": "normale"}
        )
        response = self.client.post("/api/v1/examens/sessions/", data, format="json")
        assert response.status_code == 201, response.data
        session = response.data["id"]
        data = {
            "session": session,
            "date": self.today.isoformat(),
            "heure_debut": "09:00",
            "duree_minutes": 120,
            "bareme": "20",
            "debut_soumission": (timezone.now() - timedelta(hours=1)).isoformat(),
            "fin_soumission": (timezone.now() + timedelta(hours=1)).isoformat(),
        }
        data.update(
            {"matiere": self.subject.pk, "classes": [self.classe.pk]}
            if self.secondary
            else {"ecue": self.subject.pk, "lieu": "Salle"}
        )
        response = self.client.post("/api/v1/examens/epreuves/", data, format="json")
        assert response.status_code == 201, response.data
        exam = response.data["id"]
        learner_field = "eleve" if self.secondary else "etudiant"
        response = self.client.post(
            "/api/v1/examens/resultats/",
            {"epreuve": exam, learner_field: self.learners[0].pk, "note": "14"},
            format="json",
        )
        assert response.status_code == 201, response.data
        return session, exam, response.data["id"], data

    def test_publication_requires_workflow_and_result_identity_is_immutable(self):
        _session, _exam, identifier, _payload = self.exam_result()
        url = f"/api/v1/examens/resultats/{identifier}/"
        for data in (
            {"statut": "published"},
            {"eleve" if self.secondary else "etudiant": self.learners[1].pk},
            {"note": "21"},
        ):
            assert self.client.patch(url, data, format="json").status_code == 400
        assert self.client.post(f"{url}publier/").status_code == 400
        self.client.force_authenticate(self.learners[0].user)
        assert self.client.get("/api/v1/examens/resultats/").data["count"] == 0
        self.client.force_authenticate(self.admin)
        for action in ("soumettre", "verifier", "valider", "publier"):
            response = self.client.post(f"{url}{action}/")
            assert response.status_code == 200, response.data
        result = apps.get_model("examens.ResultatExamen").objects.get(pk=identifier)
        assert result.publie_par_id == self.admin.pk
        assert result.valide_par_id == self.admin.pk
        assert result.statut == "published"
        assert self.client.patch(url, {"note": "19"}, format="json").status_code == 400
        self.client.force_authenticate(self.learners[0].user)
        assert self.client.get("/api/v1/examens/resultats/").data["count"] == 1

    def test_results_survive_parent_deletions_even_before_period_closure(self):
        session, exam, identifier, _payload = self.exam_result()
        for action in ("soumettre", "verifier", "valider", "publier"):
            assert self.client.post(f"/api/v1/examens/resultats/{identifier}/{action}/").status_code == 200
        for url in (
            f"/api/v1/examens/epreuves/{exam}/",
            f"/api/v1/examens/sessions/{session}/",
            f"/api/v1/{'eleves' if self.secondary else 'etudiants'}/{self.learners[0].pk}/",
        ):
            response = self.client.delete(url)
            assert response.status_code == 400, (url, response.data)
        assert apps.get_model("examens.ResultatExamen").objects.filter(pk=identifier).exists()
        assert self.save_grades([self.row(self.learners[0])]).status_code == 200
        assert self.client.delete(self.url).status_code == 400
        assert self.evaluation.notes.count() == 1

    def test_closure_blocks_new_exams_and_session_reopening(self):
        session, _exam, _identifier, payload = self.exam_result()
        assert self.client.post(f"/api/v1/examens/sessions/{session}/cloturer/").status_code == 200
        assert self.client.post("/api/v1/examens/epreuves/", payload, format="json").status_code == 400
        assert self.client.post(f"/api/v1/etablissement/annees/{self.year.pk}/cloturer/").status_code == 200
        assert self.client.post(f"/api/v1/examens/sessions/{session}/reouvrir/").status_code == 400

    def test_closed_year_rejects_curriculum_changes_and_individual_assignments(self):
        if self.secondary:
            subject = self.create("classes.Matiere", etablissement=self.tenant, code="NEW", nom="Nouvelle")
            base = "/api/v1/classes/programmes/"
            payload = {"classe": self.classe.pk, "matiere": subject.pk}
            custom_url = f"/api/v1/eleves/{self.learners[0].pk}/matieres-individuelles/"
            custom = {"annee_scolaire": self.year.pk, "matiere": subject.pk}
        else:
            base = "/api/v1/ue-ecue/ues/"
            payload = {
                "maquette": self.subject.ue.maquette_id,
                "semestre": self.period.pk,
                "code": "NEW",
                "nom": "Nouvelle",
                "credits_ects": "6",
            }
            custom_url = f"/api/v1/etudiants/{self.learners[0].pk}/matieres-individuelles/"
            custom = {
                "inscription_admin": self.learners[0].inscriptions_admin.get().pk,
                "semestre_cible": self.period.pk,
                "ecue": self.subject.pk,
            }
        response = self.client.post(base, payload, format="json")
        assert response.status_code == 201, response.data
        identifier = response.data["id"]
        assert self.client.post(f"/api/v1/etablissement/annees/{self.year.pk}/cloturer/").status_code == 200
        assert self.client.patch(f"{base}{identifier}/", {}, format="json").status_code == 400
        assert self.client.delete(f"{base}{identifier}/").status_code == 400
        assert self.client.post(custom_url, custom, format="json").status_code == 400
        assert self.client.post(self.base, self.payload, format="json").status_code == 400
        period_resource = "periodes" if self.secondary else "semestres"
        assert self.client.delete(f"/api/v1/etablissement/{period_resource}/{self.period.pk}/").status_code == 400

    def test_closed_session_rejects_attendance_actions_and_invitation_generation(self):
        session, exam, _identifier, _payload = self.exam_result()
        convocation = self.create(
            "examens.ConvocationExamen",
            epreuve_id=exam,
            **{"eleve" if self.secondary else "etudiant": self.learners[0]},
        )
        base = f"/api/v1/examens/convocations/{convocation.pk}/"
        present = "marquer_present" if self.secondary else "pointer"
        assert self.client.post(f"{base}{present}/", {}, format="json").status_code == 200
        assert self.client.post(f"/api/v1/examens/sessions/{session}/cloturer/").status_code == 200
        actions = ("marquer_present", "marquer_absent") if self.secondary else ("pointer",)
        for action in actions:
            response = self.client.post(f"{base}{action}/", {"statut": "absent"}, format="json")
            assert response.status_code == 400, response.data
        convocation.refresh_from_db()
        assert convocation.statut == "present"
        if not self.secondary:
            response = self.client.post(f"/api/v1/examens/epreuves/{exam}/generer_convocations/")
            assert response.status_code == 400, response.data

    def test_closed_empty_year_cannot_be_deleted(self):
        year = self.create(
            self.year_model,
            **{self.owner_field: self.tenant},
            libelle="2040",
            date_debut="2040-01-01",
            date_fin="2040-12-31",
            cloturee=True,
        )
        assert self.client.delete(f"/api/v1/etablissement/annees/{year.pk}/").status_code == 400
        assert apps.get_model(self.year_model).objects.filter(pk=year.pk).exists()

    def test_closure_requires_action_and_is_audited(self):
        url = f"/api/v1/etablissement/annees/{self.year.pk}/"
        assert self.client.patch(url, {"cloturee": True}, format="json").status_code == 400
        assert self.client.patch(url, {"en_cours": True}, format="json").status_code == 400
        assert self.client.post(f"{url}activer/").status_code == 200
        assert self.client.post(f"{url}cloturer/").status_code == 200
        events = apps.get_model("core.WorkflowEvent").objects.filter(
            app_label="etablissement", object_id=str(self.year.pk), actor=self.admin
        )
        assert set(events.values_list("action", flat=True)) == {"activation", "cloture"}

    def test_exam_definition_and_verification_cannot_be_rewritten(self):
        _session, exam, identifier, _payload = self.exam_result()
        url = f"/api/v1/examens/resultats/{identifier}/"
        assert (
            self.client.patch(f"/api/v1/examens/epreuves/{exam}/", {"bareme": "10"}, format="json").status_code == 400
        )
        assert self.client.post(f"{url}soumettre/").status_code == 200
        assert self.client.post(f"{url}verifier/").status_code == 200
        assert self.client.patch(url, {"note": "13"}, format="json").status_code == 200
        assert self.client.post(f"{url}valider/").status_code == 400

    def test_copy_moderation_cannot_overwrite_a_published_result(self):
        _session, exam, identifier, _payload = self.exam_result()
        for action in ("soumettre", "verifier", "valider", "publier"):
            assert self.client.post(f"/api/v1/examens/resultats/{identifier}/{action}/").status_code == 200
        convocation = self.create(
            "examens.ConvocationExamen",
            epreuve_id=exam,
            **{"eleve" if self.secondary else "etudiant": self.learners[0]},
        )
        copie = self.create(
            "examens.CopieExamen",
            convocation=convocation,
            statut="a_moderer",
            fichier="unused.pdf",
            empreinte_sha256="0" * 64,
            taille_octets=10,
            deposee_par=self.admin,
        )
        response = self.client.post(f"/api/v1/examens/copies/{copie.pk}/moderer/", {}, format="json")
        assert response.status_code == 400, response.data
        copie.refresh_from_db()
        result = apps.get_model("examens.ResultatExamen").objects.get(pk=identifier)
        assert result.statut == "published"
        assert result.note == 14
        assert copie.statut == "a_moderer"

    def transfer_fixture(self):
        if self.secondary:
            target = self.create(
                "classes.Classe",
                etablissement=self.tenant,
                annee_scolaire=self.year,
                niveau=self.classe.niveau,
                nom="6B",
            )
            learner = self.learners[0]
            enrollment = self.create(
                "eleves.Inscription",
                eleve=learner,
                classe=self.classe,
                annee_scolaire=self.year,
                date_inscription=self.today,
                statut="validee",
            )
            return (
                enrollment,
                target,
                f"/api/v1/eleves/{learner.pk}/changer-classe/",
                {"classe_id": target.pk, "motif": "Réorientation demandée"},
                f"/api/v1/eleves/inscriptions/{enrollment.pk}/",
                {"classe": target.pk},
            )
        target = self.create("formations.Formation", code="F2", nom="Autre", type="licence")
        enrollment = self.enroll(self.learners[2])
        return (
            enrollment,
            target,
            f"/api/v1/inscriptions/{enrollment.pk}/transferer/",
            {"formation": target.pk, "motif": "Réorientation demandée"},
            f"/api/v1/inscriptions/{enrollment.pk}/",
            {"formation": target.pk},
        )

    def test_transfer_synchronizes_enrollment_and_records_actor_reason(self):
        enrollment, target, url, payload, detail_url, patch = self.transfer_fixture()
        assert self.client.patch(detail_url, patch, format="json").status_code == 400
        assert self.client.post(url, {**payload, "motif": " "}, format="json").status_code == 400
        response = self.client.post(url, payload, format="json")
        assert response.status_code == 200, response.data
        enrollment.refresh_from_db()
        assert getattr(enrollment, "classe_id" if self.secondary else "formation_id") == target.pk
        if self.secondary:
            self.learners[0].refresh_from_db()
            assert self.learners[0].classe_actuelle_id == target.pk
            assert (
                self.client.patch(
                    f"/api/v1/eleves/{self.learners[0].pk}/",
                    {"classe_actuelle": self.classe.pk},
                    format="json",
                ).status_code
                == 400
            )
        event = apps.get_model("core.WorkflowEvent").objects.get(action="transfert")
        assert event.actor_id == self.admin.pk
        assert event.message == payload["motif"]

    def test_transfer_preserves_academic_history_and_closed_year(self):
        enrollment, _target, url, payload, _detail_url, _patch = self.transfer_fixture()
        if self.secondary:
            assert self.save_grades([self.row(self.learners[0])]).status_code == 200
        else:
            self.create(
                "etudiants.InscriptionPedagogique",
                inscription_admin=enrollment,
                semestre=self.period,
                statut="validee",
            )
        assert self.client.post(url, payload, format="json").status_code == 400
        assert self.client.post(f"/api/v1/etablissement/annees/{self.year.pk}/cloturer/").status_code == 200
        assert self.client.post(url, payload, format="json").status_code == 400
        enrollment.refresh_from_db()
        assert getattr(enrollment, "classe_id" if self.secondary else "formation_id") == (
            self.classe.pk if self.secondary else self.formation.pk
        )

    def test_workflow_actor_dates_apply_to_list_summary_and_export(self):
        Event = apps.get_model("core.WorkflowEvent")
        common = {"tenant_id": self.tenant.pk, "app_label": "etablissement", "model": "annee", "action": "cloture"}
        wanted = Event.objects.create(actor=self.admin, title="MATCH-AUDIT", **common)
        Event.objects.create(actor=self.teacher, title="OTHER-ACTOR", **common)
        old = Event.objects.create(actor=self.admin, title="OLD-AUDIT", **common)
        Event.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=3))
        Event.objects.create(
            actor=self.admin, title="PRIVATE-AUDIT", **{**common, "app_label": "core", "model": "reclamation"}
        )
        url = "/api/v1/core/workflow-events/"
        params = {
            "actor": self.admin.pk,
            "date_debut": self.today.isoformat(),
            "date_fin": self.today.isoformat(),
            "action": "cloture",
        }
        response = self.client.get(url, params)
        assert response.status_code == 200, response.data
        assert [row["id"] for row in response.data["results"]] == [wanted.pk]
        assert self.client.get(f"{url}bilan/", params).data == [{"groupe": "cloture", "nombre": 1}]
        self.tenant.configuration_academique["reports"] = [
            {
                "code": "audit",
                "label": "Audit",
                "dataset": "workflow_events",
                "fields": ["title", "actor", "created_at"],
                "formats": ["csv"],
                "allowed_filters": list(params),
            }
        ]
        self.tenant.save(update_fields=["configuration_academique"])
        response = self.client.post(f"{url}exporter/", {"report": "audit", "filters": params}, format="json")
        assert response.status_code == 200, getattr(response, "data", None)
        text = response.content.decode()
        assert "MATCH-AUDIT" in text
        assert all(value not in text for value in ("OTHER-ACTOR", "OLD-AUDIT", "PRIVATE-AUDIT"))
        for invalid in (
            {"actor": "oops"},
            {"date_debut": "2026-02-31"},
            {"date_debut": "2026-02-02", "date_fin": "2026-01-01"},
        ):
            assert self.client.get(url, invalid).status_code == 400
            assert self.client.get(f"{url}bilan/", invalid).status_code == 400
            assert (
                self.client.post(f"{url}exporter/", {"report": "audit", "filters": invalid}, format="json").status_code
                == 400
            )

    def test_enrollment_filter_does_not_mix_students(self):
        if self.secondary:
            return
        response = self.client.get("/api/v1/inscriptions/", {"etudiant": self.learners[0].pk})
        assert response.data["count"] == 1
        assert response.data["results"][0]["etudiant"] == self.learners[0].pk
        self.client.force_authenticate(self.learners[1].user)
        assert self.client.get("/api/v1/inscriptions/", {"etudiant": self.learners[0].pk}).data["count"] == 0


def test_technical_log_keeps_request_fields_without_arbitrary_extras():
    from apps.core.logging import JsonFormatter

    record = logging.LogRecord("audit", logging.INFO, "", 0, "Request completed", (), None)
    record.method = "PATCH"
    record.path = "/api/v1/notes/"
    record.status = 400
    record.duration_ms = 25
    record.actor_id = 12
    record.password = "not-for-logs"
    payload = json.loads(JsonFormatter().format(record))
    assert {key: payload[key] for key in ("method", "path", "status", "duration_ms", "actor_id")} == {
        "method": "PATCH",
        "path": "/api/v1/notes/",
        "status": 400,
        "duration_ms": 25,
        "actor_id": 12,
    }
    assert "password" not in payload
