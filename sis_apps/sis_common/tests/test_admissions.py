from unittest.mock import patch

import pytest
from django.apps import apps
from django.contrib.auth.models import Permission

from sis_common.tests.test_grade_entry import GradeEntryFixture


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
        assert not type(self.enrollment).objects.filter(
            **{self.field: self.learner, self.year_field: later_year}
        ).exists()

        assert self.client.post(f"{self.base}{renewed.pk}/valider/", {}, format="json").status_code == 200
        assert self.client.post(self.renew_url, later_payload, format="json").status_code == 400
        response = self.client.post(f"{self.base}{renewed.pk}/reinscrire/", later_payload, format="json")
        assert response.status_code == 201, response.data
        assert (
            getattr(type(self.enrollment).objects.get(pk=response.data["id"]), f"{self.year_field}_id")
            == later_year.pk
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
