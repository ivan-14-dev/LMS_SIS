"""Contract-level lifecycle regressions, executed against each variant's API."""

import json
from copy import deepcopy
from hashlib import sha256

from apps.core.models import WorkflowNotification
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models.deletion import ProtectedError
from django.test import RequestFactory

from sis_common.tests.practical_fixtures import BASE, PracticalFixture, practical_model


class PracticalTrainingTests(PracticalFixture):
    def test_publication_hours_nonself_validation_competency_revision_and_threshold_closure(self):
        self.prepare()
        snapshot = deepcopy(self.dossier["programme"])
        payload = {key: value for key, value in snapshot.items() if key != "sha256"}
        digest = sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()
        assert snapshot["sha256"] == digest
        assert snapshot["offre_source"]["mode_evaluation"] == "numeric"
        assert self.dossier["inscription"]["id"] == self.registration.pk
        assert self.dossier["tuteur_interne"]["id"] == self.tutor.pk
        assert self.report()["heures"]["minutes_validees"] == 0
        notifications = WorkflowNotification.objects.count()

        before = self.state()
        response = self.command("clore/")
        self.assert_error(response, 409, "seuils_non_atteints")
        assert {item["type"] for item in response.data["criteres_non_satisfaits"]} == {"minutes", "competence"}
        assert self.state() == before

        hour = self.record()
        assert hour["minutes"] == 120
        assert hour["statut"] == "brouillon"
        assert self.report()["heures"]["minutes_brouillon"] == 120
        response = self.command(f"heures/{hour['id']}/soumettre/", self.learner_user)
        assert response.status_code == 200, response.data
        assert self.report()["heures"]["minutes_validees"] == 0
        before = self.state()
        for user in (self.learner_user, self.manager):
            self.assert_error(self.command(f"heures/{hour['id']}/valider/", user), 403)
            assert self.state() == before
        response = self.command(f"heures/{hour['id']}/valider/", self.tutor)
        assert response.status_code == 200, response.data
        assert self.report()["heures"]["minutes_validees"] == 120

        first = self.assessment(acquise=False)
        assert first.status_code == 201, first.data
        original = practical_model("EvaluationCompetencePratique").objects.values().get(pk=first.data["evaluation"]["id"])
        assert self.report()["competences_acquises"] == 0
        before = self.state()
        self.assert_error(self.assessment(), 400, "validation_error")
        self.assert_error(self.command("clore/"), 409, "seuils_non_atteints")
        assert self.state() == before
        second = self.assessment(date_observation="2026-11-06", motif_revision="Observation complémentaire vérifiée.")
        assert second.status_code == 201, second.data
        assert second.data["evaluation"]["revision"] == 2
        assert second.data["evaluation"]["remplace_id"] == original["id"]
        assert practical_model("EvaluationCompetencePratique").objects.values().get(pk=original["id"]) == original
        report = self.report()
        assert report["competences_acquises"] == 1
        assert report["competences"][0]["evaluation"]["id"] == second.data["evaluation"]["id"]
        assert report["seuils_atteints"] is True
        assert report["cloture_reussie"] is False

        submitted = self.record(heure_debut="12:00", heure_fin="13:00")
        response = self.command(f"heures/{submitted['id']}/soumettre/", self.learner_user)
        assert response.status_code == 200, response.data
        draft = self.record(heure_debut="13:00", heure_fin="14:00")
        decisions = list(practical_model("DecisionHeurePratique").objects.order_by("pk").values())
        version = self.dossier["version"]
        response = self.command("clore/")
        assert response.status_code == 200, response.data
        assert response.data["version"] == version + 1
        assert set(response.data["heures_annulees"]) == {draft["id"], submitted["id"]}
        assert response.data["dossier"]["statut"] == "clos"
        assert response.data["dossier"]["programme"] == snapshot
        assert response.data["rapport"]["cloture_reussie"] is True
        assert response.data["rapport"]["heures"]["minutes_validees"] == 120
        assert response.data["rapport"]["heures"]["minutes_annulees"] == 120
        for previous in decisions:
            assert practical_model("DecisionHeurePratique").objects.values().get(pk=previous["id"]) == previous
        for identifier in (draft["id"], submitted["id"]):
            decision = practical_model("DecisionHeurePratique").objects.filter(heure_id=identifier).order_by("sequence").last()
            assert decision.action == "fermeture"
            assert decision.version_dossier == version + 1
        before = self.state()
        self.assert_error(self.command("heures/", self.learner_user, **self.hour_payload()), 409, "etat_incompatible")
        self.assert_error(self.assessment(motif_revision="Après clôture"), 409, "etat_incompatible")
        assert self.state() == before
        assert WorkflowNotification.objects.count() == notifications
        history = self.client.get(self.url("historique/"))
        assert history.status_code == 200, history.data
        assert history.data["count"] == self.dossier["version"]

    def test_new_publication_preserves_bound_snapshot_and_programme_scoped_revision_identity(self):
        self.prepare()
        bound = deepcopy(self.dossier["programme"])
        self.manager.attributs_acces = {
            "permission_scopes": {"stages.gerer_suivi_pratique": {"programme_id": [self.programme["id"]]}}
        }
        self.manager.save(update_fields=["attributs_acces"])
        self.login(self.manager)
        root = f"{BASE}programmes/{self.programme['id']}/"
        response = self.client.post(root + "reviser/", {
            "version": self.programme["version"], "revision_source": 1,
        }, format="json")
        assert response.status_code == 201, response.data
        revision = response.data["programme"]
        assert revision["id"] == self.programme["id"]
        response = self.client.post(root + "configurer/", {
            "version": revision["version"], "titre": "Nouvelles exigences", "minutes_requises": 900,
            "competences": [{"code": "autonomie", "label": "Autonomie"}],
        }, format="json")
        assert response.status_code == 200, response.data
        response = self.client.post(root + "publier/", {"version": response.data["version"]}, format="json")
        assert response.status_code == 200, response.data
        assert response.data["programme"]["revision_publiee"]["numero"] == 2
        assert practical_model("RevisionProgrammePratique").objects.get(pk=bound["revision_id"]).statut == "archive"
        assert self.client.get(self.url()).data["programme"] == bound
        self.complete()
        assert self.report()["seuils_atteints"] is True
        self.login(self.learner_user)
        assert self.client.get(root).status_code == 404
        assert self.client.get(root + "revisions/").status_code == 404

    def test_incomplete_programme_cannot_publish_and_bad_commands_are_atomic(self):
        self.login(self.manager)
        response = self.client.post(f"{BASE}programmes/", self.programme_payload(
            minutes_requises=0, competences=[]
        ), format="json")
        assert response.status_code == 201, response.data
        programme = response.data["programme"]
        before = self.state()
        response = self.client.post(
            f"{BASE}programmes/{programme['id']}/publier/", {"version": programme["version"]}, format="json",
        )
        self.assert_error(response, 400, "programme_incomplet")
        assert self.state() == before
        for changes in ({"curriculum": True}, {"curriculum": str(self.curriculum.pk)},
                        {"version": False}, {"competences": [{"code": "ok", "label": "OK", "weight": 1}]}):
            response = self.client.post(f"{BASE}programmes/", self.programme_payload(code="autre", **changes), format="json")
            self.assert_error(response, 400, "validation_error")
            assert self.state() == before

    def test_archived_never_published_draft_can_be_revised_without_rewriting_its_source(self):
        self.login(self.manager)
        response = self.client.post(f"{BASE}programmes/", self.programme_payload(
            minutes_requises=0, competences=[],
        ), format="json")
        assert response.status_code == 201, response.data
        programme = response.data["programme"]
        root = f"{BASE}programmes/{programme['id']}/"
        response = self.client.post(root + "archiver/", {
            "version": programme["version"], "revision": 1, "motif": "Reprendre la préparation plus tard.",
        }, format="json")
        assert response.status_code == 200, response.data
        archived = response.data["programme"]
        assert archived["revision_publiee"] is None
        assert archived["revision_courante"]["published_at"] is None
        assert archived["actions"]["can_revise"] is True
        original = practical_model("RevisionProgrammePratique").objects.values().get(
            pk=archived["revision_courante"]["id"]
        )
        response = self.client.post(root + "reviser/", {
            "version": archived["version"], "revision_source": 1,
        }, format="json")
        assert response.status_code == 201, response.data
        revised = response.data["programme"]
        assert revised["version"] == archived["version"] + 1
        assert revised["revision_courante"]["numero"] == 2
        assert revised["revision_courante"]["statut"] == "brouillon"
        assert revised["revision_courante"]["minutes_requises"] == 0
        assert revised["revision_courante"]["competences"] == []
        assert revised["revision_publiee"] is None
        assert revised["actions"]["can_revise"] is False
        assert revised["actions"]["can_open_dossier"] is False
        assert practical_model("RevisionProgrammePratique").objects.values().get(pk=original["id"]) == original

    def test_changed_then_malformed_current_offering_cannot_rewrite_or_block_bound_dossier(self):
        self.prepare()
        snapshot = deepcopy(self.dossier["programme"])
        registration_offering = deepcopy(self.registration.offre_configuration)
        opening = self.opening_payload(self.make_convention())
        root = f"{BASE}programmes/{self.programme['id']}/"
        response = self.client.post(root + "reviser/", {
            "version": self.programme["version"], "revision_source": 1,
        }, format="json")
        assert response.status_code == 201, response.data
        programme_version = response.data["version"]
        opening["programme_version"] = programme_version

        self.curriculum.offre_configuration = {
            **deepcopy(self.curriculum.offre_configuration), "assessment": {"mode": "pass_fail"},
        }
        self.curriculum.save(update_fields=["offre_configuration"])
        first = self.record(heure_fin="10:00")
        self.curriculum.offre_configuration = {"invalid_current_offering": True}
        self.curriculum.save(update_fields=["offre_configuration"])
        before = self.state()
        self.login(self.manager)
        candidates = self.client.get(root + "conventions/", {"revision": 1})
        assert candidates.status_code == 200, candidates.data
        assert candidates.data["count"] == 0
        response = self.client.post(f"{BASE}dossiers/", opening, format="json")
        self.assert_error(response, 409, "convention_modifiee")
        assert self.state() == before
        response = self.client.post(root + "publier/", {"version": programme_version}, format="json")
        self.assert_error(response, 400, "validation_error")
        assert self.state() == before

        second = self.record(heure_debut="10:00")
        for hour in (first, second):
            assert self.command(f"heures/{hour['id']}/soumettre/", self.learner_user).status_code == 200
            assert self.command(f"heures/{hour['id']}/valider/", self.tutor).status_code == 200
        assert self.assessment().status_code == 201
        report = self.report()
        assert report["programme"] == snapshot
        assert report["heures"]["minutes_requises"] == 120
        assert report["heures"]["minutes_validees"] == 120
        assert report["seuils_atteints"] is True
        detail = self.client.get(self.url())
        assert detail.status_code == 200, detail.data
        assert detail.data["programme"] == snapshot
        assert detail.data["liaisons_valides"] is True
        assert detail.data["blocages"] == []
        assert detail.data["actions"]["can_cancel"] is True
        response = self.command("clore/")
        assert response.status_code == 200, response.data
        assert response.data["rapport"]["programme"] == snapshot
        self.registration.refresh_from_db()
        assert self.registration.offre_configuration == registration_offering

    def test_stale_versions_strict_payloads_and_no_generic_mutation_leave_every_row_unchanged(self):
        self.create_programme()
        opening = self.opening_payload()
        before = self.state()
        fingerprint = opening["convention_empreinte"]
        for invalid in (int("1" * 64), f" {fingerprint}", f"{fingerprint}\n", "A" * 64):
            response = self.client.post(f"{BASE}dossiers/", {
                **opening, "convention_empreinte": invalid,
            }, format="json")
            self.assert_error(response, 400, "validation_error")
            assert self.state() == before
        self.open_dossier()
        hour = self.record()
        before = self.state()
        response = self.command(f"heures/{hour['id']}/soumettre/", self.learner_user, version=1)
        self.assert_error(response, 409, "version_perimee")
        assert response.data["current_version"] == self.dossier["version"]
        for changes in ({"version": True}, {"version": str(self.dossier["version"])},
                        {"pause_minutes": False}, {"minutes": 200}, {"statut": "validee"}):
            self.assert_error(self.command("heures/", self.learner_user, **self.hour_payload(**changes)), 400, "validation_error")
            assert self.state() == before
        self.login(self.learner_user)
        payload = self.hour_payload()
        payload.pop("version")
        self.assert_error(self.client.post(self.url("heures/"), payload, format="json"), 400, "validation_error")
        for verb in ("put", "patch", "delete"):
            response = getattr(self.client, verb)(self.url(f"heures/{hour['id']}/"), {}, format="json")
            assert response.status_code == 405, response.data
        self.assert_error(self.client.get(self.url("heures/"), {"unsupported": "value"}), 400, "validation_error")
        assert self.state() == before

    def test_malformed_live_offering_preserves_programme_reads_revision_and_archival(self):
        self.prepare()
        snapshot = deepcopy(self.dossier["programme"])
        root = f"{BASE}programmes/{self.programme['id']}/"
        self.curriculum.offre_configuration = {"invalid_current_offering": True}
        self.curriculum.save(update_fields=["offre_configuration"])
        before = self.state()
        for path in (root, f"{BASE}programmes/", root + "revisions/", root + "historique/"):
            response = self.client.get(path)
            assert response.status_code == 200, response.data
        detail = self.client.get(root).data
        assert detail["curriculum"]["offre"] is None
        assert detail["revision_publiee"]["offre_source"] == snapshot["offre_source"]
        assert self.state() == before

        response = self.client.post(root + "reviser/", {
            "version": detail["version"], "revision_source": 1,
        }, format="json")
        assert response.status_code == 201, response.data
        version = response.data["version"]
        before = self.state()
        response = self.client.post(root + "publier/", {"version": version}, format="json")
        self.assert_error(response, 400, "validation_error")
        assert self.state() == before
        for revision in (2, 1):
            response = self.client.post(root + "archiver/", {
                "version": version, "revision": revision, "motif": "Arrêt des nouvelles ouvertures.",
            }, format="json")
            assert response.status_code == 200, response.data
            assert response.data["version"] == version + 1
            version = response.data["version"]
        assert response.data["programme"]["revision_publiee"] is None
        assert response.data["programme"]["actions"]["can_open_dossier"] is False
        revisions = self.client.get(root + "revisions/").data["results"]
        published = next(row for row in revisions if row["numero"] == 1)
        assert published["statut"] == "archive"
        assert published["offre_source"] == snapshot["offre_source"]
        assert self.client.get(self.url()).data["programme"] == snapshot
        self.complete()
        assert self.command("clore/").status_code == 200
        assert self.report()["programme"] == snapshot

    def test_cancel_is_not_completion_and_preserves_validated_work(self):
        self.prepare()
        self.complete()
        draft = self.record(heure_debut="14:00", heure_fin="15:00")
        response = self.command("annuler/", motif="Interruption administrative.")
        assert response.status_code == 200, response.data
        assert response.data["heures_annulees"] == [draft["id"]]
        assert response.data["rapport"]["seuils_atteints"] is True
        assert response.data["rapport"]["cloture_reussie"] is False
        assert response.data["rapport"]["statut"] == "annule"
        assert response.data["rapport"]["heures"]["minutes_validees"] == 120
        assert response.data["dossier"]["closed_at"] is None
        assert response.data["dossier"]["cancelled_at"] is not None

    def test_linked_legacy_orm_bulk_upsert_admin_and_cascade_guards_are_narrow(self):
        self.prepare()
        self.complete()
        assert self.command("clore/").status_code == 200
        model = type(self.convention)
        unlinked = self.make_convention()
        before = self.state()
        original_missions = self.convention.missions
        self.convention.missions = "Modification structurelle interdite"
        request = RequestFactory().post("/admin/stages/conventionstage/")
        request.user = self.manager
        request.user.is_superuser = True
        model_admin = admin.site._registry.get(model) or admin.ModelAdmin(model, admin.site)
        attempts = (
            lambda: self.convention.save(),
            lambda: model.objects.filter(pk__in=[self.convention.pk, unlinked.pk]).update(missions="Changement"),
            lambda: model.objects.bulk_update([self.convention], ["missions"]),
            lambda: model.objects.bulk_create(
                [self.convention], update_conflicts=True, update_fields=["missions"], unique_fields=["id"],
            ),
            lambda: model.objects.filter(pk=unlinked.pk).bulk_create(
                [self.convention], update_conflicts=True, update_fields=["missions"], unique_fields=["id"],
            ),
            lambda: model_admin.save_model(request, self.convention, None, change=True),
            lambda: model_admin.delete_model(request, self.convention),
            lambda: model.objects.filter(pk=self.convention.pk).delete(),
            self.convention.delete,
            self.learner.delete,
        )
        for attempt in attempts:
            with self.assertRaises((ValidationError, ProtectedError)), transaction.atomic():  # noqa: PT027
                attempt()
            assert model.objects.get(pk=self.convention.pk).missions == original_missions
            assert model.objects.get(pk=unlinked.pk).missions == original_missions
            assert self.state() == before
        self.convention.refresh_from_db()
        self.convention.save()
        assert model.objects.filter(pk=self.convention.pk).update(missions=original_missions) == 1
        model.objects.bulk_update([self.convention], ["missions"])
        self.convention.pdf_path = "legacy/reissued-convention.pdf"
        model.objects.bulk_update([self.convention], ["pdf_path"])
        assert model.objects.get(pk=self.convention.pk).pdf_path == self.convention.pdf_path
        unlinked.missions = "Modification permise sans dossier"
        model.objects.bulk_update([unlinked], ["missions"])
        assert model.objects.get(pk=unlinked.pk).missions == unlinked.missions
        unlinked.missions = "Upsert legacy permis"
        model.objects.bulk_create(
            [unlinked], update_conflicts=True, update_fields=["missions"], unique_fields=["id"],
        )
        assert model.objects.get(pk=unlinked.pk).missions == unlinked.missions
        assert self.state() == before
        for name in ("ProgrammePratique", "DossierPratique", "HeurePratique",
                     "DecisionHeurePratique", "EvaluationCompetencePratique", "AuditPratique"):
            registered = admin.site._registry.get(practical_model(name))
            if registered:
                row = practical_model(name).objects.first()
                assert not registered.has_add_permission(request)
                assert not registered.has_change_permission(request, row)
                assert not registered.has_delete_permission(request, row)
