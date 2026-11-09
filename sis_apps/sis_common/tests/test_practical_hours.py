"""Wall-clock, immutable correction and learner-level serialization regressions."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event
from time import monotonic, sleep

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connection, connections, transaction
from django.test import TransactionTestCase
from django_tenants.utils import schema_context
from rest_framework.test import APIClient

from sis_common.tests.practical_fixtures import BASE, CONSULT, ENTER, PracticalFixture, practical_model


class PracticalHourTests(PracticalFixture):
    def test_midnight_split_wall_minutes_and_current_local_end_boundary(self):
        self.prepare()
        first = self.record(heure_debut="22:00", heure_fin="24:00", pause_minutes=30)
        second = self.record(date="2026-11-08", heure_debut="00:00", heure_fin="02:00")
        assert first["heure_fin"] == "24:00"
        assert first["minutes"] == 90
        assert second["minutes"] == 120
        current = self.record(date="2026-11-08", heure_debut="12:00", heure_fin="13:00")
        assert current["minutes"] == 60
        before = self.state()
        for values, code in (
            ({"heure_debut": "22:00", "heure_fin": "02:00"}, "horaire_incoherent"),
            ({"heure_debut": "24:00", "heure_fin": "24:00"}, "horaire_incoherent"),
            ({"heure_debut": "09:00:00"}, None),
            ({"heure_debut": "09:00+01:00"}, None),
            ({"heure_debut": " 09:00"}, "validation_error"),
            ({"heure_fin": "11:00 "}, "validation_error"),
            ({"heure_debut": "09:00", "heure_fin": "09:00"}, "horaire_incoherent"),
            ({"pause_minutes": 120}, "horaire_incoherent"),
            ({"date": "2026-11-08", "heure_debut": "13:00", "heure_fin": "13:01"}, "travail_futur"),
            (
                {"date": "2026-11-08", "heure_debut": "23:00", "heure_fin": "24:00", "pause_minutes": 59},
                "travail_futur",
            ),
            ({"date": "2026-11-09"}, "travail_futur"),
            ({"date": "2025-12-31"}, "hors_periode"),
        ):
            response = self.command("heures/", self.learner_user, **self.hour_payload(**values))
            self.assert_error(response, 400, code)
            assert self.state() == before

    def test_dst_gaps_folds_and_crossing_transitions_are_rejected_without_writes(self):
        self.prepare()
        before = self.state()
        for day in ("2026-03-29", "2026-10-25"):
            for start, end in (("01:30", "03:30"), ("02:15", "02:45")):
                response = self.command(
                    "heures/",
                    self.learner_user,
                    **self.hour_payload(
                        date=day,
                        heure_debut=start,
                        heure_fin=end,
                    ),
                )
                self.assert_error(response, 400, "transition_horaire")
                assert self.state() == before
        for day in ("2026-03-29", "2026-10-25"):
            hour = self.record(date=day, heure_debut="03:30", heure_fin="04:00")
            assert hour["minutes"] == 30

    def test_gross_partial_overlap_in_invisible_dossier_and_adjacency(self):
        self.prepare()
        first_dossier = self.dossier["id"]
        first = self.record(heure_fin="12:00", pause_minutes=60)
        assert first["minutes"] == 120
        assert self.command(f"heures/{first['id']}/soumettre/", self.learner_user).status_code == 200
        assert self.command(f"heures/{first['id']}/valider/", self.tutor).status_code == 200
        assert self.assessment().status_code == 201
        assert self.command("clore/").status_code == 200
        self.open_dossier(self.make_convention())
        scope = {"dossier_id": [self.dossier["id"]]}
        get_user_model().objects.filter(pk=self.learner_user.pk).update(
            attributs_acces={"permission_scopes": {CONSULT: scope, ENTER: scope}}
        )
        self.login(self.learner_user)
        assert self.client.get(f"{BASE}dossiers/{first_dossier}/").status_code == 404
        before = self.state()
        for start, end in (("09:00", "12:00"), ("08:30", "09:30"), ("11:00", "11:30"), ("11:30", "12:30")):
            response = self.command(
                "heures/",
                self.learner_user,
                **self.hour_payload(
                    heure_debut=start,
                    heure_fin=end,
                ),
            )
            self.assert_error(response, 409, "intervalle_occupe")
            assert response.data["errors"] == {}
            assert response.data["criteres_non_satisfaits"] == []
            assert "dossier_id" not in str(response.data)
            assert "heure_id" not in str(response.data)
            assert self.state() == before
        adjacent = self.record(heure_debut="12:00", heure_fin="13:00")
        assert adjacent["minutes"] == 60

    def test_replacement_and_invalidation_preserve_original_content_and_decisions(self):
        self.prepare()
        original = self.record()
        original_row = practical_model("HeurePratique").objects.values().get(pk=original["id"])
        first_decision = practical_model("DecisionHeurePratique").objects.values().get(heure_id=original["id"])
        replacement = self.command(
            f"heures/{original['id']}/remplacer/",
            self.learner_user,
            **self.hour_payload(heure_fin="10:30"),
            motif="Fin réelle corrigée.",
        )
        assert replacement.status_code == 201, replacement.data
        hour = replacement.data["heure"]
        assert hour["remplace_id"] == original["id"]
        assert replacement.data["heure_precedente"]["remplacement_id"] == hour["id"]
        assert replacement.data["heure_precedente"]["statut"] == "annulee"
        assert hour["minutes"] == 90
        original_row["statut"] = "annulee"
        assert practical_model("HeurePratique").objects.values().get(pk=original["id"]) == original_row
        assert practical_model("DecisionHeurePratique").objects.values().get(pk=first_decision["id"]) == first_decision
        before = self.state()
        self.assert_error(
            self.command(
                f"heures/{original['id']}/remplacer/",
                self.learner_user,
                **self.hour_payload(),
                motif="Encore",
            ),
            409,
            "etat_incompatible",
        )
        assert self.state() == before
        assert self.command(f"heures/{hour['id']}/soumettre/", self.learner_user).status_code == 200
        before = self.state()
        self.assert_error(
            self.command(
                f"heures/{hour['id']}/remplacer/",
                self.learner_user,
                **self.hour_payload(),
                motif="Soumise",
            ),
            409,
            "etat_incompatible",
        )
        assert self.state() == before
        assert self.command(f"heures/{hour['id']}/valider/", self.tutor).status_code == 200
        validation = (
            practical_model("DecisionHeurePratique").objects.values().get(heure_id=hour["id"], action="validation")
        )
        assert self.report()["heures"]["minutes_validees"] == 90
        before = self.state()
        self.assert_error(self.command(f"heures/{hour['id']}/invalider/", motif="Gestion sans habilitation"), 403)
        assert self.state() == before
        response = self.command(f"heures/{hour['id']}/invalider/", self.tutor, motif="Observation invalidée.")
        assert response.status_code == 200, response.data
        assert self.report()["heures"]["minutes_validees"] == 0
        assert practical_model("DecisionHeurePratique").objects.values().get(pk=validation["id"]) == validation
        assert self.record()["minutes"] == 120

    def test_current_timezone_change_blocks_work_without_reinterpreting_history(self):
        self.prepare()
        hour = self.record()
        self.tenant.fuseau_horaire = "UTC"
        self.tenant.save(update_fields=["fuseau_horaire"])
        before = self.state()
        self.assert_error(self.command(f"heures/{hour['id']}/soumettre/", self.learner_user), 409, "fuseau_modifie")
        assert self.state() == before
        self.login(self.manager)
        detail = self.client.get(self.url())
        assert detail.status_code == 200, detail.data
        assert detail.data["periode"]["fuseau_horaire"] == "Europe/Paris"
        assert "fuseau_modifie" in detail.data["blocages"]
        assert detail.data["actions"]["can_cancel"] is False
        assert self.report()["actions"]["can_cancel"] is False
        self.assert_error(self.command("annuler/", motif="Fuseau devenu incohérent"), 409, "fuseau_modifie")
        assert self.state() == before

    def test_immutable_work_and_decisions_reject_orm_bulk_and_delete_bypasses(self):
        self.prepare()
        hour = self.record()
        model = practical_model("HeurePratique")
        row = model.objects.get(pk=hour["id"])
        before = self.state()
        row.activite = "Historique falsifié"
        with self.assertRaises(ValidationError), transaction.atomic():  # noqa: PT027
            row.save()
        with self.assertRaises(ValidationError), transaction.atomic():  # noqa: PT027
            model.objects.filter(pk=row.pk).update(activite="Autre texte")
        with self.assertRaises(ValidationError), transaction.atomic():  # noqa: PT027
            model.objects.bulk_update([row], ["activite"])
        with self.assertRaises(ValidationError), transaction.atomic():  # noqa: PT027
            model.objects.bulk_create([row], update_conflicts=True, update_fields=["activite"], unique_fields=["id"])
        with self.assertRaises(ValidationError), transaction.atomic():  # noqa: PT027
            practical_model("DecisionHeurePratique").objects.filter(heure_id=row.pk).delete()
        assert self.state() == before


class PracticalLearnerLockTests(PracticalFixture):
    @classmethod
    def _fixture_setup(cls):
        TransactionTestCase._fixture_setup.__func__(cls)

    def _fixture_teardown(self):
        with schema_context(self.tenant.schema_name):
            TransactionTestCase._fixture_teardown(self)

    def test_conflicting_commands_in_distinct_dossiers_wait_for_same_existing_learner_row(self):
        assert not connection.in_atomic_block
        self.prepare()
        first_id = self.dossier["id"]
        self.open_dossier(self.make_convention())
        second_id = self.dossier["id"]
        schema, user_id = self.tenant.schema_name, self.learner_user.pk
        domain = self.get_test_tenant_domain()
        ready = [Event(), Event()]
        pids = {}
        learner_table = type(self.learner)._meta.db_table

        def record(index, dossier_id, start, end):
            def observe_learner_lock(execute, sql, params, many, context):
                if index not in pids and learner_table in sql and "FOR UPDATE" in sql:
                    assert params == (self.learner.pk,)
                    with connections["default"].cursor() as cursor:
                        cursor.execute("SELECT pg_backend_pid()")
                        pids[index] = cursor.fetchone()[0]
                    ready[index].set()
                return execute(sql, params, many, context)

            try:
                with schema_context(schema):
                    with connections["default"].cursor() as cursor:
                        cursor.execute("SET lock_timeout = '10s'")
                    client = APIClient()
                    client.defaults["SERVER_NAME"] = domain
                    client.force_authenticate(get_user_model().objects.get(pk=user_id))
                    with connections["default"].execute_wrapper(observe_learner_lock):
                        response = client.post(
                            f"{BASE}dossiers/{dossier_id}/heures/",
                            {
                                "version": 1,
                                "date": "2026-11-07",
                                "heure_debut": start,
                                "heure_fin": end,
                                "pause_minutes": 0,
                                "activite": "Saisie concurrente",
                            },
                            format="json",
                        )
                    return response.status_code, response.data
            finally:
                connections["default"].close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            with transaction.atomic():
                type(self.learner).objects.select_for_update().get(pk=self.learner.pk)
                with connection.cursor() as cursor:
                    cursor.execute("SELECT pg_backend_pid()")
                    holder_pid = cursor.fetchone()[0]
                futures = [
                    pool.submit(record, 0, first_id, "09:00", "11:00"),
                    pool.submit(record, 1, second_id, "10:00", "12:00"),
                ]
                assert all(event.wait(5) for event in ready), "Les deux requêtes doivent atteindre PostgreSQL."
                deadline, blocked = monotonic() + 5, set()
                while monotonic() < deadline:
                    with connection.cursor() as cursor:
                        cursor.execute(
                            "WITH RECURSIVE waits(origin, pid, path) AS ("
                            " SELECT pid, pid, ARRAY[pid] FROM pg_stat_activity WHERE pid IN (%s, %s)"
                            " UNION ALL"
                            " SELECT waits.origin, blocker.pid, waits.path || blocker.pid"
                            " FROM waits CROSS JOIN LATERAL unnest(pg_blocking_pids(waits.pid)) AS blocker(pid)"
                            " WHERE NOT blocker.pid = ANY(waits.path)"
                            ") SELECT DISTINCT origin FROM waits WHERE pid = %s",
                            [pids[0], pids[1], holder_pid],
                        )
                        blocked = {row[0] for row in cursor.fetchall()}
                    if blocked == set(pids.values()):
                        break
                    sleep(0.02)
                assert blocked == set(pids.values()), "Les dossiers distincts doivent verrouiller le même apprenant."
                assert not any(future.done() for future in futures)
            results = [future.result(timeout=15) for future in futures]
        assert sorted(status for status, _ in results) == [201, 409], results
        conflict = next(data for status, data in results if status == 409)
        assert conflict["code"] == "intervalle_occupe"
        assert conflict["errors"] == {}
        assert conflict["current_version"] is None
        assert practical_model("HeurePratique").objects.count() == 1
        assert practical_model("DecisionHeurePratique").objects.count() == 1
        assert practical_model("AuditPratique").objects.filter(action="heure_creation").count() == 1
        assert sorted(practical_model("DossierPratique").objects.values_list("version", flat=True)) == [1, 2]
