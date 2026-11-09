from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.apps import apps
from django.conf import settings
from django.contrib.auth.models import Permission
from django.db import transaction
from django.test import SimpleTestCase
from django.urls import resolve
from django_tenants.utils import schema_context
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIRequestFactory, force_authenticate

from sis_common.tests.test_grade_entry import GradeEntryFixture


class AdmissionRouteTests(SimpleTestCase):
    def test_interruption_actions_and_protected_deletion_are_routed_in_each_variant(self):
        base = "/api/v1/eleves/inscriptions/" if settings.SIS_VARIANT == "secondaire" else "/api/v1/inscriptions/"
        for operation in ("suspendre", "reprendre", "abandonner"):
            with self.subTest(operation=operation):
                callback = resolve(f"{base}1/{operation}/").func
                assert callback.actions == {"post": operation}
        assert resolve(f"{base}1/").func.actions["delete"] == "destroy"
        assert resolve(f"{base}catalogue/").func.actions["get"] == "catalogue"


class AdmissionsTests(GradeEntryFixture):
    def setUp(self):
        super().setUp()
        self.learner = self.learners[0]
        self.field = "eleve" if self.secondary else "etudiant"
        self.target_field = "classe" if self.secondary else "formation"
        if self.secondary:
            self.enrollment = self.create(
                "eleves.Inscription",
                eleve=self.learner,
                classe=self.classe,
                annee_scolaire=self.year,
                date_inscription=self.today,
                statut="validee",
            )
        else:
            self.enrollment = self.learner.inscriptions_admin.get()
        self.base = "/api/v1/eleves/inscriptions/" if self.secondary else "/api/v1/inscriptions/"
        self.new_year = self.create(
            self.year_model,
            **{self.owner_field: self.tenant},
            libelle="Nouvelle année",
            date_debut=self.year.date_debut.replace(year=self.today.year + 1),
            date_fin=self.year.date_fin.replace(year=self.today.year + 1),
        )
        self.target = (
            self.create(
                "classes.Classe",
                etablissement=self.tenant,
                annee_scolaire=self.new_year,
                niveau=self.classe.niveau,
                nom="Nouvelle classe",
            )
            if self.secondary
            else self.create("formations.Formation", code="NEW-FORMATION", nom="Autre cursus", type="licence")
        )
        self.next_payload = {
            self.year_field: self.new_year.pk,
            self.target_field: self.target.pk,
            "date_inscription": self.today.isoformat(),
            "motif": "Poursuite dans un nouveau cursus",
        }
        self.renew_url = f"{self.base}{self.enrollment.pk}/reinscrire/"

    def renew(self):
        response = self.client.post(self.renew_url, self.next_payload, format="json")
        assert response.status_code == 201, response.data
        return type(self.enrollment).objects.get(pk=response.data["id"])

    def test_closed_origin_can_progress_without_mutating_previous_results_or_dossier(self):
        assert self.save_grades([self.row(self.learner)]).status_code == 200
        previous = {
            "grade": self.note_model.objects.get(**{self.learner_field: self.learner.pk}).valeur,
            "target": getattr(self.enrollment, f"{self.target_field}_id"),
            "rules": self.enrollment.offre_configuration,
        }
        self.year.cloturee = True
        self.year.save(update_fields=["cloturee"])
        renewed = self.renew()
        assert renewed.statut == ("en_cours" if self.secondary else "provisoire")
        assert renewed.pk != self.enrollment.pk
        assert getattr(renewed, f"{self.field}_id") == self.learner.pk
        assert self.client.post(f"{self.base}{renewed.pk}/valider/", {}, format="json").status_code == 200
        self.enrollment.refresh_from_db()
        assert getattr(self.enrollment, f"{self.target_field}_id") == previous["target"]
        assert self.enrollment.offre_configuration == previous["rules"]
        assert self.note_model.objects.get(**{self.learner_field: self.learner.pk}).valeur == previous["grade"]
        if self.secondary:
            self.learner.refresh_from_db()
            assert self.learner.classe_actuelle_id == self.classe.pk
        else:
            assert self.enrollment.inscriptions_peda.count() == 1
            assert renewed.inscriptions_peda.count() == 0
        history = self.client.get(f"{self.base}{self.enrollment.pk}/historique/")
        assert any(event["action"] == "reinscription_initiee" for event in history.data)
        assert self.client.post(self.renew_url, self.next_payload, format="json").status_code == 400

    def test_closed_target_and_overlapping_year_are_rejected(self):
        self.new_year.cloturee = True
        self.new_year.save(update_fields=["cloturee"])
        assert self.client.post(self.renew_url, self.next_payload, format="json").status_code == 400
        self.new_year.cloturee = False
        self.new_year.date_debut = self.year.date_fin
        self.new_year.save(update_fields=["cloturee", "date_debut"])
        assert self.client.post(self.renew_url, self.next_payload, format="json").status_code == 400
        assert not type(self.enrollment).objects.filter(**{self.year_field: self.new_year}).exists()

    def test_non_object_reenrollment_payload_is_rejected_without_mutation_and_can_be_retried(self):
        history_url = f"{self.base}{self.enrollment.pk}/historique/"
        previous_history = self.client.get(history_url).data
        previous_enrollment = self.client.get(f"{self.base}{self.enrollment.pk}/").data
        for payload in ([], [{"motif": "Poursuite"}], "Poursuite", 1, True):
            with self.subTest(payload=payload):
                response = self.client.post(self.renew_url, payload, format="json")
                assert response.status_code == 400, response.data
                assert "detail" in response.data
        assert self.client.get(f"{self.base}{self.enrollment.pk}/").data == previous_enrollment
        assert self.client.get(history_url).data == previous_history
        assert not type(self.enrollment).objects.filter(**{self.year_field: self.new_year}).exists()

        self.client.force_authenticate(self.learner.user)
        assert self.client.post(self.renew_url, [], format="json").status_code == 403
        self.client.force_authenticate(self.admin)
        renewed = self.renew()
        assert renewed.statut == ("en_cours" if self.secondary else "provisoire")
        assert self.client.post(self.renew_url, self.next_payload, format="json").status_code == 400
        assert type(self.enrollment).objects.filter(**{self.year_field: self.new_year}).count() == 1

    def test_replay_from_older_origin_is_rejected_but_latest_validated_origin_can_progress(self):
        later_year = self.create(
            self.year_model,
            **{self.owner_field: self.tenant},
            libelle="Année suivante",
            date_debut=self.year.date_debut.replace(year=self.today.year + 2),
            date_fin=self.year.date_fin.replace(year=self.today.year + 2),
        )
        later_target = (
            self.create(
                "classes.Classe",
                etablissement=self.tenant,
                annee_scolaire=later_year,
                niveau=self.classe.niveau,
                nom="Classe suivante",
            )
            if self.secondary
            else self.target
        )
        later_payload = {
            **self.next_payload,
            self.year_field: later_year.pk,
            self.target_field: later_target.pk,
        }
        renewed = self.renew()
        assert self.client.post(self.renew_url, later_payload, format="json").status_code == 400
        assert (
            not type(self.enrollment).objects.filter(**{self.field: self.learner, self.year_field: later_year}).exists()
        )

        assert self.client.post(f"{self.base}{renewed.pk}/valider/", {}, format="json").status_code == 200
        assert self.client.post(self.renew_url, later_payload, format="json").status_code == 400
        response = self.client.post(f"{self.base}{renewed.pk}/reinscrire/", later_payload, format="json")
        assert response.status_code == 201, response.data
        assert (
            getattr(type(self.enrollment).objects.get(pk=response.data["id"]), f"{self.year_field}_id") == later_year.pk
        )

    def test_decisions_cannot_be_forged_and_approved_records_cannot_be_refused(self):
        forged = {**self.next_payload, self.field: self.learner.pk, "statut": "validee"}
        assert self.client.post(self.base, forged, format="json").status_code == 400
        assert (
            self.client.patch(f"{self.base}{self.enrollment.pk}/", {"statut": "refusee"}, format="json").status_code
            == 400
        )
        assert (
            self.client.post(
                f"{self.base}{self.enrollment.pk}/refuser/", {"motif": "Refus tardif"}, format="json"
            ).status_code
            == 400
        )
        renewed = self.renew()
        url = f"{self.base}{renewed.pk}/"
        assert self.client.post(f"{url}refuser/", {"motif": "  "}, format="json").status_code == 400
        response = self.client.post(f"{url}refuser/", {"motif": "Dossier incomplet"}, format="json")
        assert response.status_code == 200, response.data
        renewed.refresh_from_db()
        assert renewed.statut == "refusee"
        assert self.client.post(f"{url}valider/", {}, format="json").status_code == 400
        assert self.client.post(f"{url}annuler/", {"motif": "Autre décision"}, format="json").status_code == 400

    def test_cancellation_and_notifications_are_atomic(self):
        notifications = apps.get_model("core.WorkflowNotification")
        with patch.object(notifications.objects, "create", side_effect=RuntimeError("notification failed")):
            with pytest.raises(RuntimeError, match="notification failed"):
                self.renew()
        assert not type(self.enrollment).objects.filter(**{self.year_field: self.new_year}).exists()
        renewed = self.renew()
        response = self.client.post(f"{self.base}{renewed.pk}/annuler/", {"motif": "Demande retirée"}, format="json")
        assert response.status_code == 200, response.data
        renewed.refresh_from_db()
        assert renewed.statut == "annulee"

    def test_learner_staff_cannot_decide_and_destination_scope_is_enforced(self):
        user = self.learner.user
        user.is_staff = True
        user.save(update_fields=["is_staff"])
        self.client.force_authenticate(user)
        assert self.client.get(self.base).data["count"] == 1
        assert self.client.post(self.renew_url, self.next_payload, format="json").status_code == 403
        clerk = type(self.admin).objects.create_user("admissions-clerk", role="autre", etablissement=self.tenant)
        meta = self.enrollment._meta
        permission = f"{meta.app_label}.change_{meta.model_name}"
        clerk.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label=meta.app_label,
                codename__in=[f"view_{meta.model_name}", f"change_{meta.model_name}"],
            )
        )
        clerk.attributs_acces = {"permission_scopes": {permission: {"annees": [self.year.pk]}}}
        clerk.save(update_fields=["attributs_acces"])
        self.client.force_authenticate(clerk)
        assert self.client.post(self.renew_url, self.next_payload, format="json").status_code == 403
        assert not type(self.enrollment).objects.filter(**{self.year_field: self.new_year}).exists()

    def test_authenticated_candidate_deposits_first_dossier_once_with_audit(self):
        candidate = self.learners[2]
        self.client.force_authenticate(candidate.user)
        catalogue = self.client.get(f"{self.base}catalogue/")
        assert catalogue.status_code == 200, catalogue.data
        target_id = self.classe.pk if self.secondary else self.formation.pk
        assert target_id in [item["id"] for item in catalogue.data["targets"]]
        url = f"{self.base}deposer/"
        payload = {
            self.year_field: self.year.pk,
            self.target_field: self.classe.pk if self.secondary else self.formation.pk,
        }

        response = self.client.post(url, {**payload, "motif": "Première admission"}, format="json")
        assert response.status_code == 201, response.data
        enrollment = type(self.enrollment).objects.get(pk=response.data["id"])
        assert getattr(enrollment, f"{self.field}_id") == candidate.pk
        assert enrollment.statut == ("en_cours" if self.secondary else "provisoire")
        assert enrollment.date_inscription == self.today
        if self.secondary:
            assert enrollment.motif == "Première admission"
        else:
            assert enrollment.regime == candidate.regime
        history = self.client.get(f"{self.base}{enrollment.pk}/historique/")
        assert history.status_code == 200, history.data
        assert [event["action"] for event in history.data] == ["admission_deposee"]
        assert self.client.post(url, payload, format="json").status_code == 400
        assert self.client.get(f"{self.base}catalogue/").status_code == 400
        assert type(self.enrollment).objects.filter(**{self.field: candidate}).count() == 1
        assert self.client.post(self.base, {**payload, self.field: candidate.pk}, format="json").status_code == 403
        assert self.client.post(f"{self.base}{enrollment.pk}/valider/", {}, format="json").status_code == 403
        self.client.force_authenticate(self.learner.user)
        assert self.client.post(url, self.next_payload, format="json").status_code == 400
        assert not type(self.enrollment).objects.filter(**{self.year_field: self.new_year}).exists()

    def test_first_admission_catalogue_exposes_only_choices_not_school_records(self):
        candidate = self.learners[2]
        self.client.force_authenticate(candidate.user)
        general_url = "/api/v1/classes/classes/" if self.secondary else "/api/v1/formations/formations/"
        assert self.client.get(general_url).data["count"] == 0
        self.new_year.cloturee = True
        self.new_year.save(update_fields=["cloturee"])
        if not self.secondary:
            self.target.actif = False
            self.target.save(update_fields=["actif"])
            path = self.create("formations.Parcours", formation=self.formation, code="ADMISSION", nom="Parcours")
            self.create("formations.Parcours", formation=self.target, code="CLOSED", nom="Masqué")
        response = self.client.get(f"{self.base}catalogue/")
        assert response.status_code == 200, response.data
        assert response["Cache-Control"] == "private, no-store"
        assert response.data["years"] == [{"id": self.year.pk, "libelle": self.year.libelle}]
        assert response.data["targets"] == (
            [{"id": self.classe.pk, "nom": self.classe.nom, "annee_scolaire": self.year.pk}]
            if self.secondary
            else [{"id": self.formation.pk, "nom": self.formation.nom}]
        )
        assert response.data["paths"] == (
            [] if self.secondary else [{"id": path.pk, "nom": path.nom, "formation": self.formation.pk}]
        )
        assert self.client.get(general_url).data["count"] == 0

    def test_first_admission_catalogue_requires_an_active_same_tenant_learner_profile(self):
        url = f"{self.base}catalogue/"
        assert self.client.get(url).status_code == 403
        self.client.force_authenticate(self.teacher)
        assert self.client.get(url).status_code == 403
        candidate = self.learners[2]
        self.client.force_authenticate(candidate.user)
        candidate.user.is_active = False
        assert self.client.get(url).status_code == 403
        candidate.user.is_active = True
        candidate.user.etablissement_id = self.tenant.pk + 1
        assert self.client.get(url).status_code == 403
        candidate.user.etablissement_id = self.tenant.pk
        unverified = type(candidate.user).objects.create_user(
            "admission-without-profile", role=candidate.user.role, etablissement=self.tenant
        )
        self.client.force_authenticate(unverified)
        assert self.client.get(url).status_code == 403

    def test_candidate_cannot_deposit_without_proof_or_choose_another_identity_or_closed_year(self):
        candidate = self.learners[2]
        url = f"{self.base}deposer/"
        payload = {
            self.year_field: self.year.pk,
            self.target_field: self.classe.pk if self.secondary else self.formation.pk,
        }
        self.client.force_authenticate(user=None)
        assert self.client.post(url, payload, format="json").status_code in (401, 403)
        self.client.force_authenticate(self.admin)
        assert self.client.post(url, payload, format="json").status_code == 403
        self.client.force_authenticate(candidate.user)
        assert self.client.post(url, {**payload, self.field: self.learners[1].pk}, format="json").status_code == 400
        assert self.client.post(url, {**payload, "statut": "validee"}, format="json").status_code == 400
        if self.secondary:
            response = self.client.post(url, {**payload, self.target_field: self.target.pk}, format="json")
            assert response.status_code == 400
        assert not type(self.enrollment).objects.filter(**{self.field: candidate}).exists()
        self.year.cloturee = True
        self.year.save(update_fields=["cloturee"])
        assert self.client.post(url, payload, format="json").status_code == 400
        assert not type(self.enrollment).objects.filter(**{self.field: candidate}).exists()
        unverified = type(self.admin).objects.create_user(
            "admission-without-profile", role=candidate.user.role, etablissement=self.tenant
        )
        self.client.force_authenticate(unverified)
        assert self.client.post(url, payload, format="json").status_code == 403

    def test_candidate_deposit_and_notification_are_atomic(self):
        candidate = self.learners[2]
        self.client.force_authenticate(candidate.user)
        payload = {
            self.year_field: self.year.pk,
            self.target_field: self.classe.pk if self.secondary else self.formation.pk,
        }
        notifications = apps.get_model("core.WorkflowNotification")
        with patch.object(notifications.objects, "create", side_effect=RuntimeError("notification failed")):
            with pytest.raises(RuntimeError, match="notification failed"):
                self.client.post(f"{self.base}deposer/", payload, format="json")
        assert not type(self.enrollment).objects.filter(**{self.field: candidate}).exists()

    def transition(self, operation, payload=None):
        return self.client.post(
            f"{self.base}{self.enrollment.pk}/{operation}/",
            {"motif": "Décision motivée de la scolarité"} if payload is None else payload,
            format="json",
        )

    def test_suspension_resume_preserve_closed_results_and_reject_duplicate_commands(self):
        self.learner.statut = "redoublant"
        self.learner.save(update_fields=["statut"])
        assert self.save_grades([self.row(self.learner)]).status_code == 200
        note = self.note_model.objects.get(**{self.learner_field: self.learner.pk})
        original = (note.valeur, self.enrollment.offre_configuration)
        period_closed = "cloturee" if hasattr(self.period, "cloturee") else "cloture"
        setattr(self.period, period_closed, True)
        self.period.save(update_fields=[period_closed])
        response = self.transition("suspendre")
        assert response.status_code == 200, response.data
        self.learner.refresh_from_db()
        assert self.learner.statut == "suspendu"
        if self.secondary:
            assert self.learner.classe_actuelle_id is None
        else:
            assert self.enrollment.inscriptions_peda.get().statut == "validee"
        assert self.transition("suspendre").status_code == 400
        response = self.transition("reprendre")
        assert response.status_code == 200, response.data
        assert self.transition("reprendre").status_code == 400
        self.learner.refresh_from_db()
        self.enrollment.refresh_from_db()
        note.refresh_from_db()
        assert self.learner.statut == "redoublant"
        assert self.enrollment.statut == "validee"
        assert (note.valeur, self.enrollment.offre_configuration) == original
        if self.secondary:
            assert self.learner.classe_actuelle_id == self.classe.pk
        history = self.client.get(f"{self.base}{self.enrollment.pk}/historique/").data
        assert [event["action"] for event in history] == ["reprendre", "suspendre"]
        assert all(event["message"] == "Décision motivée de la scolarité" for event in history)

    def test_suspended_learner_cannot_receive_new_grades_and_can_resume(self):
        assert self.transition("suspendre").status_code == 200
        assert self.save_grades([self.row(self.learner)]).status_code == 400
        assert not self.note_model.objects.filter(**{self.learner_field: self.learner.pk}).exists()
        assert self.transition("reprendre").status_code == 200
        assert self.save_grades([self.row(self.learner)]).status_code == 200

    def test_resume_rechecks_school_capacity_without_losing_suspension(self):
        if not self.secondary:
            self.skipTest("La capacité de classe est un invariant du secondaire.")
        assert self.transition("suspendre").status_code == 200
        self.classe.effectif_max = 1
        self.classe.save(update_fields=["effectif_max"])
        response = self.transition("reprendre")
        assert response.status_code == 400, response.data
        assert "classe" in response.data
        self.enrollment.refresh_from_db()
        assert self.enrollment.statut == "suspendue"
        other = self.learners[1]
        other.classe_actuelle = None
        other.save(update_fields=["classe_actuelle"])
        assert self.transition("reprendre").status_code == 200

    def test_resume_rejects_closed_expired_and_future_years(self):
        assert self.transition("suspendre").status_code == 200
        self.year.cloturee = True
        self.year.save(update_fields=["cloturee"])
        assert self.transition("reprendre").status_code == 400
        self.year.cloturee = False
        self.year.save(update_fields=["cloturee"])
        for today in (self.year.date_fin + timedelta(days=1), self.year.date_debut - timedelta(days=1)):
            with self.subTest(today=today), patch("sis_common.admissions.timezone.localdate", return_value=today):
                assert self.transition("reprendre").status_code == 400
        self.enrollment.refresh_from_db()
        assert self.enrollment.statut == "suspendue"
        assert self.transition("reprendre").status_code == 200

    def test_abandonment_is_final_for_this_year_but_allows_next_year_reenrollment(self):
        assert self.transition("suspendre").status_code == 200
        assert self.transition("abandonner").status_code == 200
        for operation in ("reprendre", "suspendre", "abandonner"):
            assert self.transition(operation).status_code == 400
        assert self.client.delete(f"{self.base}{self.enrollment.pk}/").status_code == 400
        self.year.cloturee = True
        self.year.save(update_fields=["cloturee"])
        renewed = self.renew()
        assert self.client.post(f"{self.base}{renewed.pk}/valider/", {}, format="json").status_code == 200
        self.learner.refresh_from_db()
        self.enrollment.refresh_from_db()
        assert self.learner.statut == "abandon"
        assert self.enrollment.statut == "abandonnee"
        assert self.client.post(self.renew_url, self.next_payload, format="json").status_code == 400

    def test_lifecycle_rejects_malformed_payloads_and_direct_status_bypasses(self):
        for payload in ([], 1, "motif", {}, {"motif": " "}, {"motif": "Justifié", "statut": "validee"}):
            with self.subTest(payload=payload):
                assert self.transition("suspendre", payload).status_code == 400
        for state in ("suspendue", "abandonnee"):
            assert (
                self.client.patch(f"{self.base}{self.enrollment.pk}/", {"statut": state}, format="json").status_code
                == 400
            )
        learner_url = f"/api/v1/{'eleves' if self.secondary else 'etudiants'}/{self.learner.pk}/"
        assert self.client.patch(learner_url, {"statut": "suspendu"}, format="json").status_code == 400
        assert self.transition("suspendre").status_code == 200
        assert self.client.patch(learner_url, {"statut": "inscrit"}, format="json").status_code == 400
        assert (
            self.client.patch(
                f"{self.base}{self.enrollment.pk}/",
                {"date_inscription": (self.today - timedelta(days=1)).isoformat()},
                format="json",
            ).status_code
            == 400
        )

    def test_lifecycle_is_atomic_with_notifications_and_requires_a_scoped_operator(self):
        notifications = apps.get_model("core.WorkflowNotification")
        with patch.object(notifications.objects, "create", side_effect=RuntimeError("notification failed")):
            with pytest.raises(RuntimeError, match="notification failed"):
                self.transition("suspendre")
        self.enrollment.refresh_from_db()
        self.learner.refresh_from_db()
        assert self.enrollment.statut == "validee"
        assert self.learner.statut != "suspendu"
        assert self.client.get(f"{self.base}{self.enrollment.pk}/historique/").data == []
        for user in (self.learner.user, self.teacher):
            self.client.force_authenticate(user)
            assert self.transition("suspendre").status_code == 403
        clerk = type(self.admin).objects.create_user("lifecycle-clerk", role="autre", etablissement=self.tenant)
        meta = self.enrollment._meta
        permission = f"{meta.app_label}.change_{meta.model_name}"
        clerk.user_permissions.add(
            Permission.objects.get(content_type__app_label=meta.app_label, codename=f"change_{meta.model_name}")
        )
        clerk.attributs_acces = {"permission_scopes": {permission: {"annees": [self.new_year.pk]}}}
        clerk.save(update_fields=["attributs_acces"])
        self.client.force_authenticate(clerk)
        assert self.transition("suspendre").status_code == 404

    def test_expired_admission_cannot_be_submitted_or_validated_even_if_year_not_closed(self):
        candidate = self.learners[2]
        payload = {
            self.year_field: self.year.pk,
            self.target_field: self.classe.pk if self.secondary else self.formation.pk,
        }
        self.client.force_authenticate(candidate.user)
        response = self.client.post(f"{self.base}deposer/", payload, format="json")
        assert response.status_code == 201, response.data
        with patch("sis_common.admissions.timezone.localdate", return_value=self.year.date_fin + timedelta(days=1)):
            self.client.force_authenticate(self.admin)
            assert self.client.post(f"{self.base}{response.data['id']}/valider/", {}, format="json").status_code == 400
        enrollment = type(self.enrollment).objects.get(pk=response.data["id"])
        assert enrollment.statut == ("en_cours" if self.secondary else "provisoire")

    def test_foreign_tenant_cannot_transition_or_read_an_enrollment_history(self):
        foreign = type(self.tenant)(schema_name="foreign_schooling")
        self.setup_tenant(foreign)
        foreign.auto_create_schema = False
        with schema_context("public"):
            foreign.save()
        for operation in ("suspendre", "reprendre", "abandonner", "historique"):
            url = f"{self.base}{self.enrollment.pk}/{operation}/"
            request = (
                APIRequestFactory().get(url)
                if operation == "historique"
                else APIRequestFactory().post(url, {"motif": "Autre établissement"}, format="json")
            )
            request.tenant = foreign
            force_authenticate(request, user=self.admin)
            response = resolve(url).func(request)
            assert response.status_code in (403, 404), response.data
        self.enrollment.refresh_from_db()
        assert self.enrollment.statut == "validee"
        assert self.client.get(f"{self.base}{self.enrollment.pk}/historique/").data == []

    def test_create_rechecks_uniqueness_when_another_dossier_was_saved_after_validation(self):
        view_class = resolve(self.base).func.cls
        view = view_class()
        request = SimpleNamespace(tenant=self.tenant, user=self.admin, method="POST")
        payload = {key: value for key, value in self.next_payload.items() if key != "motif"}
        serializer = view.serializer_class(data={**payload, self.field: self.learner.pk}, context={"request": request})
        serializer.is_valid(raise_exception=True)
        destination = self.renew()
        with transaction.atomic(), pytest.raises(ValidationError, match="existe déjà"):
            view.save_academic(serializer)
        assert (
            type(self.enrollment).objects.filter(**{self.field: self.learner, self.year_field: self.new_year}).get().pk
            == destination.pk
        )

    def test_suspension_and_elapsed_year_block_individual_subject_changes(self):
        prefix = "eleves" if self.secondary else "etudiants"
        url = f"/api/v1/{prefix}/{self.learner.pk}/matieres-individuelles/"
        payload = (
            {"annee_scolaire": self.year.pk, "matiere": self.subject.pk}
            if self.secondary
            else {
                "inscription_admin": self.enrollment.pk,
                "semestre_cible": self.period.pk,
                "ecue": self.subject.pk,
            }
        )
        assert self.transition("suspendre").status_code == 200
        assert self.client.post(url, payload, format="json").status_code == 400
        assert self.transition("reprendre").status_code == 200
        response = self.client.post(url, payload, format="json")
        assert response.status_code == 201, response.data
        identifier = response.data["id"]
        remove_url = f"/api/v1/{prefix}/{self.learner.pk}/retirer-matiere-individuelle/"
        assert self.transition("suspendre").status_code == 200
        assert self.client.post(remove_url, {"affectation_id": identifier}, format="json").status_code == 400
        assert self.transition("reprendre").status_code == 200
        with patch("sis_common.admissions.timezone.localdate", return_value=self.year.date_fin + timedelta(days=1)):
            assert self.client.post(remove_url, {"affectation_id": identifier}, format="json").status_code == 400
        assert self.client.post(remove_url, {"affectation_id": identifier}, format="json").status_code == 204

    def test_initial_admission_does_not_allow_grades_before_administrative_validation(self):
        candidate = self.learners[2]
        self.client.force_authenticate(candidate.user)
        response = self.client.post(
            f"{self.base}deposer/",
            {
                self.year_field: self.year.pk,
                self.target_field: self.classe.pk if self.secondary else self.formation.pk,
            },
            format="json",
        )
        assert response.status_code == 201, response.data
        enrollment = type(self.enrollment).objects.get(pk=response.data["id"])
        if not self.secondary:
            choices = self.create(
                "etudiants.InscriptionPedagogique",
                inscription_admin=enrollment,
                semestre=self.period,
                statut="validee",
            )
            choices.ues.add(self.subject.ue)
        self.client.force_authenticate(self.admin)
        assert self.save_grades([self.row(candidate)]).status_code == 400
        assert self.client.post(f"{self.base}{enrollment.pk}/valider/", {}, format="json").status_code == 200
        assert self.save_grades([self.row(candidate)]).status_code == 200
