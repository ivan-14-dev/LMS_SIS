"""Fresh tenant, named-permission, assignment and terminal ACL regressions."""

from copy import deepcopy
from datetime import UTC, datetime

from apps.core.models import ModuleConfiguration, WorkflowEvent
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.urls import resolve
from django_tenants.utils import schema_context
from rest_framework.test import APIRequestFactory, force_authenticate

from sis_common.tests.practical_fixtures import (
    BASE,
    CONSULT,
    ENTER,
    EVALUATE,
    MANAGE,
    NOW,
    PDF,
    VALIDATE,
    PracticalFixture,
    practical_model,
)


class PracticalAccessTests(PracticalFixture):
    def test_absent_and_empty_scopes_work_but_provided_malformed_restrictions_deny(self):
        self.prepare()
        self.login(self.learner_user)
        allowed = (
            {},
            {"permission_scopes": {}},
            {"permission_scopes": {CONSULT: {}}},
            {"permission_scopes": {MANAGE: {"unknown": []}}},
            {"permission_scopes": {CONSULT: {"dossier_id": [self.dossier["id"]]}}},
            {"permission_scopes": {CONSULT: {"programme_id": [self.programme["id"]]}}},
        )
        self.learner_user.user_permissions.remove(self.learner_user.user_permissions.get(codename=ENTER.split(".")[1]))
        for attributes in allowed:
            get_user_model().objects.filter(pk=self.learner_user.pk).update(attributs_acces=attributes)
            response = self.client.get(self.url())
            assert response.status_code == 200, (attributes, response.data)
            assert self.client.get(f"{BASE}dossiers/").data["count"] == 1
        denied = (
            {"permission_scopes": None},
            {"permission_scopes": []},
            *(
                {"permission_scopes": {CONSULT: value}}
                for value in (
                    None,
                    [],
                    {"unknown": [1]},
                    {"dossier_id": []},
                    {"dossier_id": [True]},
                    {"dossier_id": ["1"]},
                    {"dossier_id": [0]},
                    {"dossier_id": [-1]},
                    {"dossier_id": None},
                )
            ),
        )
        before = self.state()
        for attributes in denied:
            get_user_model().objects.filter(pk=self.learner_user.pk).update(attributs_acces=attributes)
            self.assert_error(self.client.get(self.url()), 404, "not_found")
            self.assert_error(self.client.get(f"{BASE}dossiers/"), 403)
            assert self.state() == before
        get_user_model().objects.filter(pk=self.learner_user.pk).update(
            attributs_acces={
                "permission_scopes": {CONSULT: {"dossier_id": [self.dossier["id"]], "programme_id": [999999]}}
            }
        )
        self.assert_error(self.client.get(self.url()), 404)
        assert self.client.get(f"{BASE}dossiers/").data["count"] == 0

    def test_creation_never_discards_programme_or_dossier_restrictions(self):
        self.create_programme()
        opening = self.opening_payload()
        before = self.state()
        for scope in ({"programme_id": [self.programme["id"]]}, {"dossier_id": [999999]}):
            get_user_model().objects.filter(pk=self.manager.pk).update(
                attributs_acces={"permission_scopes": {MANAGE: scope}}
            )
            response = self.client.post(f"{BASE}programmes/", self.programme_payload(code="restricted"), format="json")
            self.assert_error(response, 403)
            assert self.state() == before
        response = self.client.post(f"{BASE}dossiers/", opening, format="json")
        self.assert_error(response, 403)
        assert self.state() == before
        get_user_model().objects.filter(pk=self.manager.pk).update(
            attributs_acces={"permission_scopes": {MANAGE: {"programme_id": [self.programme["id"]]}}}
        )
        response = self.client.post(f"{BASE}dossiers/", opening, format="json")
        assert response.status_code == 201, response.data

    def test_named_permission_and_actor_assignment_are_independently_required(self):
        self.prepare()
        self.login(self.outsider)
        self.assert_error(self.client.get(self.url()), 404)
        self.assert_error(
            self.client.post(f"{BASE}programmes/", self.programme_payload(code="staff"), format="json"), 403
        )
        self.grant(self.outsider, CONSULT, ENTER, VALIDATE, EVALUATE)
        self.assert_error(self.client.get(self.url()), 404)
        self.grant(self.outsider, MANAGE)
        assert self.client.get(self.url()).status_code == 200
        before = self.state()
        self.assert_error(self.command("heures/", self.outsider, **self.hour_payload()), 403)
        self.assert_error(
            self.command(
                "competences/securite/evaluer/",
                self.outsider,
                acquise=True,
                contexte_professionnel="Sans affectation",
                date_observation="2026-11-07",
            ),
            403,
        )
        assert self.state() == before
        self.partner.user_permissions.clear()
        self.login(self.partner)
        self.assert_error(self.client.get(self.url()), 404)
        self.assert_error(self.client.get(f"{BASE}dossiers/"), 403)

    def test_permissions_account_institution_and_module_are_rechecked_without_relogin(self):
        self.prepare()
        self.login(self.partner)
        assert self.partner.has_perm(CONSULT)
        assert self.client.get(self.url()).status_code == 200
        self.partner.user_permissions.clear()
        self.assert_error(self.client.get(self.url()), 404)
        self.grant(self.partner, CONSULT)
        assert self.client.get(self.url()).status_code == 200
        get_user_model().objects.filter(pk=self.partner.pk).update(is_active=False)
        self.assert_error(self.client.get(self.url()), 403)
        get_user_model().objects.filter(pk=self.partner.pk).update(is_active=True)
        for changes, restoration in (
            ({"enabled": {"sis.practical_training": False}}, {"enabled": {"sis.practical_training": True}}),
            (
                {"enabled": {"sis.practical_training": True, "core.notifications": False}},
                {"enabled": {"sis.practical_training": True}},
            ),
        ):
            ModuleConfiguration.objects.filter(etablissement=self.tenant).update(**changes)
            self.assert_error(self.client.get(self.url()), 403)
            ModuleConfiguration.objects.filter(etablissement=self.tenant).update(**restoration)
        type(self.tenant).objects.filter(pk=self.tenant.pk).update(actif=False)
        try:
            self.assert_error(self.client.get(self.url()), 403)
        finally:
            type(self.tenant).objects.filter(pk=self.tenant.pk).update(actif=True)
        assert self.client.get(self.url()).status_code == 200

    def test_public_schema_and_foreign_or_ownerless_superusers_never_get_local_access(self):
        self.prepare()
        self.manager.is_superuser = True
        self.manager.save(update_fields=["is_superuser"])
        callback = resolve(self.url()).func
        request = APIRequestFactory().get(self.url())
        request.tenant = self.tenant
        force_authenticate(request, self.manager)
        before = self.state()
        with schema_context("public"):
            self.assert_error(callback(request), 403)
        assert connection.schema_name == self.tenant.schema_name
        assert self.state() == before
        foreign = type(self.tenant)(schema_name="practical_foreign")
        self.setup_tenant(foreign)
        foreign.auto_create_schema = False
        with schema_context("public"):
            foreign.save()
        if self.secondary:
            year = self.create(
                "etablissement.AnneeScolaire",
                etablissement=foreign,
                libelle="Externe 2026",
                date_debut=self.year.date_debut,
                date_fin=self.year.date_fin,
            )
            level = self.create("etablissement.Niveau", etablissement=foreign, code="EXT", libelle="Externe")
            source = self.create(
                "classes.Classe",
                etablissement=foreign,
                niveau=level,
                annee_scolaire=year,
                nom="Externe",
            )
        else:
            faculty = self.create("structure.Faculte", universite=foreign, code="EXT", nom="Externe")
            department = self.create("structure.Departement", faculte=faculty, code="EXT", nom="Externe")
            source = self.create(
                "formations.Formation", departement=department, code="EXT", nom="Externe", type="licence"
            )
        foreign_user = get_user_model().objects.create_user("foreign-stage-manager", etablissement=foreign)
        foreign_programme = practical_model("ProgrammePratique").objects.create(
            etablissement=foreign,
            curriculum=source,
            code="foreign",
            cree_par=foreign_user,
        )
        practical_model("RevisionProgrammePratique").objects.create(
            programme=foreign_programme,
            numero=1,
            titre="Exigences externes",
            minutes_requises=120,
            competences=[{"code": "externe", "label": "Externe"}],
            cree_par=foreign_user,
        )
        self.login(self.manager)
        self.assert_error(self.client.get(f"{BASE}programmes/{foreign_programme.pk}/"), 404)
        before = self.state()
        try:
            for owner in (foreign.pk, None):
                get_user_model().objects.filter(pk=self.manager.pk).update(etablissement_id=owner)
                self.login(get_user_model().objects.get(pk=self.manager.pk))
                self.assert_error(self.client.get(self.url()), 403)
        finally:
            get_user_model().objects.filter(pk=self.manager.pk).update(etablissement=self.tenant)
        assert self.state() == before

    def test_profile_account_rebinding_never_transfers_frozen_learner_access(self):
        self.prepare()
        hour = self.record()
        assert self.command(f"heures/{hour['id']}/soumettre/", self.learner_user).status_code == 200
        self.grant(self.outsider, CONSULT, ENTER)
        self.learner.user = self.outsider
        try:
            with transaction.atomic():
                self.learner.save(update_fields=["user"])
        except ValidationError:
            self.learner.refresh_from_db()
        before = self.state()
        self.login(self.outsider)
        self.assert_error(self.client.get(self.url()), 404)
        if self.learner.user_id == self.outsider.pk:
            self.login(self.learner_user)
            self.assert_error(self.client.get(self.url()), 404)
            self.assert_error(self.command(f"heures/{hour['id']}/valider/", self.tutor), 409, "liaison_modifiee")
        assert self.state() == before

    def test_native_local_superuser_can_decide_only_as_assigned_nonself_tutor(self):
        self.prepare()
        self.tutor.user_permissions.clear()
        self.tutor.groups.clear()
        get_user_model().objects.filter(pk=self.tutor.pk).update(
            is_superuser=True, attributs_acces={"permission_scopes": None}
        )
        hour = self.record()
        assert self.command(f"heures/{hour['id']}/soumettre/", self.learner_user).status_code == 200
        response = self.command(f"heures/{hour['id']}/valider/", self.tutor)
        assert response.status_code == 200, response.data
        assert self.assessment().status_code == 201
        before = self.state()
        get_user_model().objects.filter(pk=self.tutor.pk).update(is_active=False)
        self.login(self.tutor)
        self.assert_error(self.client.get(self.url()), 403)
        assert self.state() == before
        get_user_model().objects.filter(pk=self.tutor.pk).update(is_active=True)
        own = self.record(self.tutor, heure_debut="12:00", heure_fin="13:00")
        assert self.command(f"heures/{own['id']}/soumettre/", self.tutor).status_code == 200
        before = self.state()
        self.assert_error(self.command(f"heures/{own['id']}/valider/", self.tutor), 403)
        for user in (self.manager, self.learner_user):
            get_user_model().objects.filter(pk=user.pk).update(is_superuser=True)
            self.assert_error(self.command(f"heures/{own['id']}/valider/", user), 403)
        assert self.state() == before

    def test_partner_expiry_revocation_and_independent_management_are_separate_paths(self):
        self.prepare()
        self.login(self.partner)
        assert self.client.get(self.url()).status_code == 200
        self.clock.return_value = datetime(2027, 1, 2, 12, tzinfo=UTC)
        for tail in ("", "rapport/", "historique/"):
            self.assert_error(self.client.get(self.url(tail)), 404)
        assert self.client.get(f"{BASE}dossiers/").data["count"] == 0
        self.grant(self.partner, MANAGE)
        get_user_model().objects.filter(pk=self.partner.pk).update(
            attributs_acces={"permission_scopes": {MANAGE: {"dossier_id": [self.dossier["id"]]}}}
        )
        for tail in ("", "rapport/", "historique/"):
            assert self.client.get(self.url(tail)).status_code == 200
        response = self.command("partenaire/revoquer/", self.partner, motif="Fin d'affectation externe.")
        assert response.status_code == 200, response.data
        self.login(self.partner)
        assert self.client.get(self.url()).status_code == 200
        before = self.state()
        self.assert_error(
            self.command(
                "competences/securite/evaluer/",
                self.partner,
                acquise=True,
                contexte_professionnel="Accès administratif seulement",
                date_observation="2026-11-07",
            ),
            403,
        )
        assert self.state() == before
        self.partner.user_permissions.remove(self.partner.user_permissions.get(codename=MANAGE.split(".")[1]))
        self.assert_error(self.client.get(self.url()), 404)

    def test_generic_workflow_excludes_practical_history_but_preserves_legacy_stages(self):
        self.prepare()
        for name in (
            "programmepratique",
            "revisionprogrammepratique",
            "dossierpratique",
            "heurepratique",
            "decisionheurepratique",
            "evaluationcompetencepratique",
            "auditpratique",
            "conventionstage",
        ):
            event = WorkflowEvent.objects.create(
                actor=self.manager,
                tenant_id=self.tenant.pk,
                app_label="stages",
                model=name,
                object_id="1",
                object_repr="Suivi confidentiel",
                action="practical_privacy_regression",
                title="Suivi",
                metadata={"private_marker": "do-not-export"},
            )
            if name == "conventionstage":
                legacy_id = event.pk
        self.manager.is_superuser = True
        self.manager.save(update_fields=["is_superuser"])
        self.login(self.manager)
        query = {"app_label": "stages", "action": "practical_privacy_regression"}
        response = self.client.get("/api/v1/core/workflow-events/", query)
        assert response.status_code == 200, response.data
        assert response.data["count"] == 1
        assert str(response.data["results"][0]["id"]) == str(legacy_id)
        summary = self.client.get("/api/v1/core/workflow-events/bilan/", query)
        assert summary.status_code == 200, summary.data
        assert summary.data == [{"groupe": "practical_privacy_regression", "nombre": 1}]


class PracticalTerminalACLTests(PracticalFixture):
    def check_terminal_revocation(self, action):
        self.prepare()
        self.complete()
        uploaded = self.upload(payload=self.hour_payload(heure_debut="14:00", heure_fin="15:00"))
        assert uploaded.status_code == 201, uploaded.data
        download = uploaded.data["heure"]["preuve"]["download_url"]
        response = self.command(action + "/", **({"motif": "Arrêt administratif."} if action == "annuler" else {}))
        assert response.status_code == 200, response.data
        before_dto = deepcopy(response.data["dossier"])
        assert before_dto["actions"]["can_revoke_partner"] is True
        assert not any(
            before_dto["actions"][key] for key in ("can_enter_hours", "can_evaluate", "can_close", "can_cancel")
        )
        self.learner.statut = "diplome"
        self.learner.save(update_fields=["statut"])
        self.registration.statut = "annulee"
        self.registration.save(update_fields=["statut"])
        if not self.secondary:
            self.curriculum.actif = False
            self.curriculum.save(update_fields=["actif"])
        get_user_model().objects.filter(pk=self.partner.pk).update(is_active=False)
        self.clock.return_value = datetime(2027, 2, 1, 12, tzinfo=UTC)
        before = self.state()
        before_report = self.report()
        response = self.command("partenaire/revoquer/", motif="Retrait de l'accès au dossier historique.")
        assert response.status_code == 200, response.data
        assert response.data["version"] == before_dto["version"] + 1
        assert response.data["heures_annulees"] == []
        assert response.data["dossier"]["actions"]["can_revoke_partner"] is False
        after = self.state()
        for name in before["rows"]:
            if name not in ("DossierPratique", "AuditPratique"):
                assert after["rows"][name] == before["rows"][name]
        assert after["files"] == before["files"]
        old_row, new_row = before["rows"]["DossierPratique"][0], after["rows"]["DossierPratique"][0]
        changed = {key for key in old_row if old_row[key] != new_row[key]}
        assert changed == {"version", "partenaire_revoque_le", "partenaire_revoque_par_id", "motif_revocation"}
        new_audits = [row for row in after["rows"]["AuditPratique"] if row not in before["rows"]["AuditPratique"]]
        assert len(new_audits) == 1
        assert new_audits[0]["action"] == "partenaire_revocation"
        assert new_audits[0]["acteur_id"] == self.manager.pk
        assert new_audits[0]["version"] == new_row["version"]
        assert after["rows"]["AuditPratique"] == before["rows"]["AuditPratique"] + new_audits
        after_report = self.report()
        assert {k: v for k, v in after_report.items() if k != "version"} == {
            k: v for k, v in before_report.items() if k != "version"
        }
        get_user_model().objects.filter(pk=self.partner.pk).update(is_active=True)
        self.clock.return_value = NOW
        self.login(self.partner)
        for url in (self.url(), self.url("rapport/"), self.url("historique/"), download):
            self.assert_error(self.client.get(url), 404)
        self.grant(self.partner, MANAGE)
        downloaded = self.client.get(download)
        assert downloaded.status_code == 200
        assert b"".join(downloaded.streaming_content) == PDF
        self.assert_error(self.command("partenaire/revoquer/", motif="Deuxième retrait"), 409, "etat_incompatible")
        assert self.state() == after

    def test_closed_acl_revocation_changes_only_metadata_one_version_and_one_audit(self):
        self.check_terminal_revocation("clore")

    def test_cancelled_acl_revocation_remains_available_after_historic_activity_ends(self):
        self.check_terminal_revocation("annuler")

    def test_terminal_acl_denials_do_not_change_files_decisions_versions_or_audit(self):
        self.prepare()
        assert self.command("annuler/", motif="Arrêt").status_code == 200
        before = self.state()
        self.assert_error(self.command("partenaire/revoquer/", motif="Retrait", version=1), 409, "version_perimee")
        self.assert_error(self.command("partenaire/revoquer/", motif=" "), 400, "validation_error")
        self.assert_error(self.command("partenaire/revoquer/", self.tutor, motif="Non gestionnaire"), 403)
        self.grant(self.outsider, MANAGE)
        self.outsider.attributs_acces = {"permission_scopes": {MANAGE: {"dossier_id": [999999]}}}
        self.outsider.save(update_fields=["attributs_acces"])
        self.assert_error(self.command("partenaire/revoquer/", self.outsider, motif="Hors périmètre"), 404)
        assert self.state() == before

    def test_terminal_dossier_without_partner_does_not_gain_an_acl_assignment(self):
        if not self.secondary:
            self.contact.user = None
            self.contact.save(update_fields=["user"])
        self.create_programme()
        payload = self.opening_payload()
        if self.secondary:
            payload["partenaire_utilisateur"] = None
        response = self.client.post(f"{BASE}dossiers/", payload, format="json")
        assert response.status_code == 201, response.data
        self.dossier = response.data["dossier"]
        assert self.command("annuler/", motif="Fin sans partenaire").status_code == 200
        before = self.state()
        assert self.dossier["actions"]["can_revoke_partner"] is False
        self.assert_error(self.command("partenaire/revoquer/", motif="Pas d'affectation"), 409, "etat_incompatible")
        assert self.state() == before
