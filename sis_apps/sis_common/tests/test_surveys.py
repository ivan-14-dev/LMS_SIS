from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from apps.core.models import InstitutionalSurvey, ModuleConfiguration, SurveyRecipient, SurveyResponse, WorkflowEvent
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.utilisateurs.models import GroupLifecycle
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.db import IntegrityError, connection, connections, transaction
from django.test import TransactionTestCase
from django_tenants.utils import schema_context
from rest_framework.test import APIClient

MANAGEMENT = "/api/v1/core/enquetes/"
PORTAL = "/api/v1/portail/enquetes/"
PERMISSION = "core.gerer_enquete_institutionnelle"


class SurveyFixture(TenantAPITestCase):
    def setUp(self):
        self.users = get_user_model()
        self.manager = self.user("survey-manager", "personnel_administratif")
        self.teacher = self.user("survey-teacher", "enseignant", is_staff=True)
        self.learner = self.user("survey-learner", "eleve" if settings.SIS_VARIANT == "secondaire" else "etudiant")
        self.parent = self.user("survey-parent", "parent")
        self.outsider = self.user("survey-outsider", "personnel_administratif")
        self.permission = Permission.objects.get(content_type__app_label="core", codename=PERMISSION.split(".")[1])
        self.manager.user_permissions.add(self.permission)
        ModuleConfiguration.objects.update_or_create(
            etablissement=self.tenant, defaults={"enabled": {"sis.surveys": True}}
        )
        self.payload = {
            "titre": "Avis sur les services",
            "description": "Enquête interne nominative.",
            "politique": "nominative",
            "questionnaire": [
                {"id": "avis", "libelle": "Votre avis", "type": "texte"},
                {"id": "accueil", "libelle": "Accueil", "type": "choix", "choix": ["Bien", "À améliorer"]},
            ],
            "destinataires": [self.learner.pk, self.parent.pk, self.teacher.pk],
        }
        self.answers = {"politique": "nominative", "reponses": {"avis": "Avis privé", "accueil": "Bien"}}

    def user(self, username, role, **kwargs):
        return self.users.objects.create_user(username, role=role, etablissement=self.tenant, **kwargs)

    def login(self, user):
        self.client.force_authenticate(self.users.objects.get(pk=user.pk))

    def create_survey(self):
        self.login(self.manager)
        response = self.client.post(MANAGEMENT, self.payload, format="json")
        assert response.status_code == 201, response.data
        self.survey = response.data
        return response

    def url(self, action="", portal=False):
        return f"{PORTAL if portal else MANAGEMENT}{self.survey['id']}/{action}"

    def mutate(self, action, **data):
        self.login(self.manager)
        response = self.client.post(self.url(action), {"version": self.survey["version"], **data}, format="json")
        if response.status_code == 200:
            self.survey = response.data
        return response

    def publish(self):
        self.create_survey()
        response = self.mutate("publier/")
        assert response.status_code == 200, response.data

    def respond(self, user=None, payload=None):
        self.login(user or self.learner)
        return self.client.post(self.url("repondre/", portal=True), payload or self.answers, format="json")

    def foreign_tenant(self):
        foreign = type(self.tenant)(schema_name="survey_foreign")
        self.setup_tenant(foreign)
        foreign.auto_create_schema = False
        with schema_context("public"):
            foreign.save()
        return foreign


class InstitutionalSurveyTests(SurveyFixture):
    def test_four_audiences_keep_answers_and_recipients_private(self):
        partner = self.user("survey-partner", "partenaire")
        self.payload["destinataires"].append(partner.pk)
        self.create_survey()
        candidates = self.client.get(f"{MANAGEMENT}candidats/?q=survey-partner")
        assert candidates.status_code == 200, candidates.data
        assert [(row["id"], row["profil"]) for row in candidates.data["results"]] == [(partner.pk, "Partenaire")]
        self.login(self.learner)
        assert self.client.get(PORTAL).data["count"] == 0
        assert self.client.get(self.url(portal=True)).status_code == 404
        assert self.mutate("publier/").status_code == 200
        for user in (self.learner, self.parent, self.teacher, partner):
            self.login(user)
            assert self.client.get(PORTAL).data["count"] == 1
            assert self.client.get(f"{PORTAL}capacites/").data["can_manage"] is False
            detail = self.client.get(self.url(portal=True))
            assert detail.status_code == 200, detail.data
            assert detail.data["politique"] == "nominative"
            assert "Aucun anonymat" in detail.data["information"]
            assert "destinataires" not in detail.data
            assert "reponses" not in detail.data
            assert detail.data["ma_reponse"] is None
            assert self.client.get(self.url()).status_code == 403
            assert self.client.get(self.url("resultats/")).status_code == 403
            response = self.respond(
                user, {**self.answers, "reponses": {**self.answers["reponses"], "avis": user.username}}
            )
            assert response.status_code == 201, response.data
            assert response.data["ma_reponse"]["reponses"]["avis"] == user.username
            assert response.data["peut_repondre"] is False
            assert self.client.patch(self.url(portal=True), self.answers, format="json").status_code == 405
        assert self.respond(partner).status_code == 409
        self.login(self.manager)
        results = self.client.get(self.url("resultats/"))
        assert results.status_code == 200, results.data
        assert results.data["reponses_recues"] == 4
        assert results.data["choix"][0]["comptages"][0] == {"choix": "Bien", "total": 4}
        assert {row["destinataire"]["id"] for row in results.data["reponses"]} == set(self.payload["destinataires"])
        assert self.client.get(self.url(portal=True)).status_code == 404
        assert self.mutate("fermer/").status_code == 200
        self.login(self.parent)
        assert self.client.get(self.url(portal=True)).data["ma_reponse"]["reponses"]["avis"] == self.parent.username

    def test_unique_response_and_closure_never_overwrite(self):
        self.publish()
        assert self.respond().status_code == 201
        duplicate = self.respond(
            payload={**self.answers, "reponses": {**self.answers["reponses"], "avis": "Overwrite"}}
        )
        assert duplicate.status_code == 409
        assert "déjà répondu" in str(duplicate.data)
        assert SurveyResponse.objects.get().reponses["avis"] == "Avis privé"
        with self.assertRaises(IntegrityError), transaction.atomic():
            SurveyResponse.objects.create(
                destinataire=SurveyRecipient.objects.get(utilisateur=self.learner), reponses={}
            )
        assert self.mutate("fermer/").status_code == 200
        closed = self.respond(self.parent)
        assert closed.status_code == 409
        assert "fermée" in str(closed.data)
        assert SurveyResponse.objects.count() == 1
        assert self.mutate("publier/").status_code == 409
        assert self.mutate("fermer/").status_code == 409

    def test_configuration_is_versioned_and_frozen_after_publication(self):
        self.create_survey()
        assert self.mutate("configurer/", **{**self.payload, "titre": "Brouillon modifié"}).status_code == 200
        assert self.mutate("configurer/", **{**self.payload, "version": 1}).status_code == 409
        assert self.mutate("publier/").status_code == 200
        assert (
            self.mutate(
                "configurer/", **{**self.payload, "questionnaire": self.payload["questionnaire"][:1]}
            ).status_code
            == 409
        )
        assert self.mutate("configurer/", **{**self.payload, "destinataires": [self.outsider.pk]}).status_code == 409
        assert len(InstitutionalSurvey.objects.get().questionnaire) == 2
        self.login(self.manager)
        assert self.client.patch(self.url(), {"titre": "Bypass"}, format="json").status_code == 405
        assert self.client.delete(self.url()).status_code == 405

    def test_outsider_revoked_and_inactive_accounts_cannot_read_or_submit(self):
        self.publish()
        assert self.respond(self.outsider).status_code == 404
        assert self.client.get(PORTAL).data["count"] == 0
        assert self.respond().status_code == 201
        assert self.mutate("revoquer/", destinataire=self.learner.pk).status_code == 200
        assert self.respond().status_code == 404
        assert self.client.get(self.url(portal=True)).status_code == 404
        assert self.client.get(PORTAL).data["count"] == 0
        self.login(self.manager)
        results = self.client.get(self.url("resultats/")).data
        assert results["reponses_recues"] == 1
        assert results["reponses"][0]["revoked_at"] is not None
        self.parent.is_active = False
        self.parent.save(update_fields=["is_active"])
        assert self.respond(self.parent).status_code == 403
        assert SurveyResponse.objects.count() == 1

    def test_permissions_are_administrable_scoped_and_revocable_without_role_grants(self):
        self.publish()
        for user in (self.teacher, self.outsider):
            self.login(user)
            assert self.client.get(MANAGEMENT).status_code == 403
            assert self.client.get(f"{MANAGEMENT}candidats/?q=survey").status_code == 403
            assert self.client.post(MANAGEMENT, self.payload, format="json").status_code == 403
        self.manager.user_permissions.clear()
        group = Group.objects.create(name="Enquêtes habilitées")
        group.permissions.add(self.permission)
        self.manager.groups.add(group)
        self.login(self.manager)
        assert self.client.get(self.url("resultats/")).status_code == 200
        lifecycle = GroupLifecycle.objects.create(group=group, actif=False)
        self.login(self.manager)
        assert self.client.get(self.url("resultats/")).status_code == 403
        lifecycle.actif = True
        lifecycle.save(update_fields=["actif"])
        self.login(self.manager)
        assert self.client.get(self.url("resultats/")).status_code == 200
        self.manager.attributs_acces = {"permission_scopes": {PERMISSION: {"etablissement_id": [self.tenant.pk + 100]}}}
        self.manager.save(update_fields=["attributs_acces"])
        self.login(self.manager)
        assert self.client.get(self.url("resultats/")).status_code == 403
        assert self.client.get(f"{PORTAL}capacites/").data["can_manage"] is False
        self.manager.attributs_acces = {"permission_scopes": {PERMISSION: {"etablissement_id": [self.tenant.pk]}}}
        self.manager.save(update_fields=["attributs_acces"])
        self.login(self.manager)
        assert self.client.get(self.url("resultats/")).status_code == 200
        group.permissions.clear()
        self.login(self.manager)
        assert self.client.get(self.url()).status_code == 403
        assert self.client.get(self.url("resultats/")).status_code == 403
        assert self.mutate("fermer/").status_code == 403

    def test_foreign_tenant_relations_and_disabled_module_fail_closed(self):
        self.publish()
        foreign = self.foreign_tenant()
        self.parent.etablissement = foreign
        self.parent.save(update_fields=["etablissement"])
        assert self.respond(self.parent).status_code == 403
        self.login(self.manager)
        candidates = self.client.get(f"{MANAGEMENT}candidats/?q=survey").data["results"]
        assert self.parent.pk not in {row["id"] for row in candidates}
        assert self.client.post(MANAGEMENT, self.payload, format="json").status_code == 400
        self.manager.etablissement = foreign
        self.manager.save(update_fields=["etablissement"])
        self.login(self.manager)
        assert self.client.get(self.url("resultats/")).status_code == 403
        InstitutionalSurvey.objects.filter(pk=self.survey["id"]).update(etablissement=foreign)
        assert self.respond().status_code == 404
        assert self.client.get(PORTAL).data["count"] == 0
        ModuleConfiguration.objects.filter(etablissement=self.tenant).update(enabled={"sis.surveys": False})
        assert self.client.get(PORTAL).status_code == 403
        assert self.respond().status_code == 403
        assert SurveyResponse.objects.count() == 0

    def test_selection_revalidates_active_users_at_publication(self):
        self.create_survey()
        self.teacher.is_active = False
        self.teacher.save(update_fields=["is_active"])
        assert self.mutate("publier/").status_code == 400
        assert InstitutionalSurvey.objects.get().statut == "brouillon"
        self.login(self.manager)
        candidates = self.client.get(f"{MANAGEMENT}candidats/?q=survey").data["results"]
        assert self.teacher.pk not in {row["id"] for row in candidates}
        assert self.learner.pk in {row["id"] for row in candidates}
        assert all(set(row) == {"id", "nom", "profil"} for row in candidates)
        assert self.client.get(f"{MANAGEMENT}candidats/").status_code == 400

    def test_private_events_and_atomic_audit_never_include_answers(self):
        self.publish()
        before = WorkflowEvent.objects.filter(model="institutionalsurvey").count()
        with patch("sis_common.surveys.record_workflow_event", side_effect=RuntimeError("Audit unavailable")):
            with self.assertRaises(RuntimeError):
                self.respond()
        assert SurveyResponse.objects.count() == 0
        assert WorkflowEvent.objects.filter(model="institutionalsurvey").count() == before
        assert self.respond().status_code == 201
        assert not WorkflowEvent.objects.filter(model="institutionalsurvey").exclude(metadata={}).exists()
        self.outsider.user_permissions.add(
            Permission.objects.get(content_type__app_label="core", codename="view_workflowevent")
        )
        self.login(self.outsider)
        assert self.client.get("/api/v1/core/workflow-events/?model=institutionalsurvey").data["count"] == 0

    def test_invalid_answers_do_not_create_partial_responses(self):
        self.publish()
        for answers in (
            {},
            {"avis": "seule"},
            {"avis": "avis", "accueil": "Inconnu"},
            {**self.answers["reponses"], "extra": "non"},
        ):
            assert self.respond(payload={"politique": "nominative", "reponses": answers}).status_code == 400
        assert self.respond(payload={**self.answers, "politique": "anonyme"}).status_code == 400
        assert self.respond(payload={**self.answers, "utilisateur": self.parent.pk}).status_code == 400
        assert SurveyResponse.objects.count() == 0


class SurveyConcurrencyTests(SurveyFixture):
    @classmethod
    def _fixture_setup(cls):
        TransactionTestCase._fixture_setup.__func__(cls)

    def _fixture_teardown(self):
        with schema_context(self.tenant.schema_name):
            TransactionTestCase._fixture_teardown(self)

    def race(self, commands):
        assert not connection.in_atomic_block
        barrier = Barrier(len(commands))

        def mutate(command):
            actor_id, url, payload = command
            try:
                with schema_context(self.tenant.schema_name):
                    actor = self.users.objects.get(pk=actor_id)
                    client = APIClient(SERVER_NAME=self.get_test_tenant_domain())
                    client.force_authenticate(actor)
                    barrier.wait(timeout=10)
                    return client.post(url, payload, format="json").status_code
            finally:
                connections["default"].close()

        with ThreadPoolExecutor(max_workers=len(commands)) as pool:
            return list(pool.map(mutate, commands))

    def test_duplicate_submissions_serialize_to_one_response(self):
        self.publish()
        command = (self.learner.pk, self.url("repondre/", portal=True), self.answers)
        assert sorted(self.race([command, command])) == [201, 409]
        assert SurveyResponse.objects.count() == 1
        assert WorkflowEvent.objects.filter(action="enquete_reponse_recue").count() == 1

    def test_closure_serializes_with_submission(self):
        self.publish()
        result = self.race(
            [
                (self.manager.pk, self.url("fermer/"), {"version": self.survey["version"]}),
                (self.learner.pk, self.url("repondre/", portal=True), self.answers),
            ]
        )
        assert result[0] == 200
        assert result[1] in (201, 409)
        assert InstitutionalSurvey.objects.get().statut == "fermee"
        assert SurveyResponse.objects.count() == int(result[1] == 201)
        assert self.respond(self.parent).status_code == 409

    def test_revocation_serializes_with_submission(self):
        self.publish()
        result = self.race(
            [
                (
                    self.manager.pk,
                    self.url("revoquer/"),
                    {"version": self.survey["version"], "destinataire": self.learner.pk},
                ),
                (self.learner.pk, self.url("repondre/", portal=True), self.answers),
            ]
        )
        assert result[0] == 200
        assert result[1] in (201, 404)
        assert SurveyResponse.objects.count() == int(result[1] == 201)
        assert self.respond().status_code == 404
