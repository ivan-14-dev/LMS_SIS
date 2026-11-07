import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from unittest.mock import patch
from uuid import uuid4

from apps.core.models import (
    PedagogicalProject,
    ProjectContribution,
    ProjectDelivery,
    ProjectEvaluation,
    ProjectMembership,
    ProjectMilestone,
    ProjectTeam,
    WorkflowEvent,
)
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import SuspiciousFileOperation
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection, connections
from django.test import TransactionTestCase, override_settings
from django_tenants.utils import schema_context
from rest_framework.test import APIClient

from sis_common.exam_files import PrivateExamStorage

BASE = "/api/v1/core/projets/"
MODULES = "/api/v1/etablissement/current/modules/"


class ProjectFixture(TenantAPITestCase):
    def setUp(self):
        self.users = get_user_model()
        self.admin = self.user("project-admin", "super_admin", is_superuser=True)
        self.manager = self.user("project-manager", "enseignant")
        self.evaluator = self.user("project-evaluator", "enseignant")
        self.other_evaluator = self.user("project-other-evaluator", "enseignant")
        self.staff = self.user("project-staff", "enseignant", is_staff=True)
        role = "eleve" if settings.SIS_VARIANT == "secondaire" else "etudiant"
        self.alice = self.user("project-alice", role)
        self.anne = self.user("project-anne", role)
        self.bob = self.user("project-bob", role)
        self.outsider = self.user("project-outsider", role)
        self.grant(self.manager, "gerer_projet_pedagogique")
        self.grant(self.evaluator, "evaluer_projet_pedagogique")
        self.grant(self.other_evaluator, "evaluer_projet_pedagogique")
        self.storage_folder = (Path.cwd() / ".project-test-files" / uuid4().hex).resolve()
        self.storage_folder.mkdir(parents=True)
        self.addCleanup(shutil.rmtree, self.storage_folder)
        field = ProjectDelivery._meta.get_field("fichier")
        storage = field.storage
        field.storage = PrivateExamStorage(location=self.storage_folder)
        self.addCleanup(setattr, field, "storage", storage)
        self.storage = field.storage
        self.client.force_authenticate(self.admin)
        assert self.client.get(BASE).status_code == 403
        self.toggle(True)
        self.project = None

    def user(self, username, role, **kwargs):
        return self.users.objects.create_user(username, role=role, etablissement=self.tenant, **kwargs)

    def grant(self, user, codename):
        user.user_permissions.add(Permission.objects.get(content_type__app_label="core", codename=codename))
        for attr in ("_perm_cache", "_user_perm_cache", "_group_perm_cache"):
            user.__dict__.pop(attr, None)

    def login(self, user):
        self.client.force_authenticate(self.users.objects.get(pk=user.pk))

    def toggle(self, enabled):
        self.login(self.admin)
        current = self.client.get(MODULES)
        assert current.status_code == 200, current.data
        response = self.client.patch(
            MODULES,
            {
                "revision": current.data["revision"],
                "enabled": {"sis.projects": enabled},
                "reason": "Qualification projets",
            },
            format="json",
        )
        assert response.status_code == 200, response.data

    def create_project(self, mode="collectif"):
        self.login(self.manager)
        response = self.client.post(
            BASE,
            {
                "titre": "Projet énergie",
                "description": "Concevoir et argumenter une solution.",
                "mode": mode,
                "responsable": self.manager.pk,
                "evaluateurs": [self.evaluator.pk],
            },
            format="json",
        )
        assert response.status_code == 201, response.data
        self.project = response.data
        return response.data

    def url(self, tail=""):
        return f"{BASE}{self.project['id']}/{tail}"

    def mutate(self, tail, user=None, **data):
        self.login(user or self.manager)
        response = self.client.post(self.url(tail), {"version": self.project["version"], **data}, format="json")
        if response.status_code < 300:
            self.project["version"] = response.data["version"]
        return response

    def prepare(self, mode="collectif"):
        self.create_project(mode)
        response = self.mutate(
            "jalons/",
            titre="Prototype",
            consignes="Rapport PDF",
            ordre=1,
            echeance="2030-05-01T12:00:00Z",
            bareme="20.00",
        )
        assert response.status_code == 201, response.data
        self.milestone = response.data["jalon"]
        members = [self.alice.pk, self.anne.pk] if mode == "collectif" else [self.alice.pk]
        response = self.mutate("equipes/", nom="Équipe A", membres=members)
        assert response.status_code == 201, response.data
        self.team = response.data["equipe"]
        response = self.mutate("equipes/", nom="Équipe B", membres=[self.bob.pk])
        assert response.status_code == 201, response.data
        self.other_team = response.data["equipe"]

    def team_path(self, tail="", team=None):
        return f"equipes/{(team or self.team)['id']}/{tail}"

    def upload(self, user=None, team=None, **values):
        self.login(user or self.alice)
        response = self.client.post(
            self.url(self.team_path("livrables/", team)),
            {
                "version": self.project["version"],
                "jalon": self.milestone["id"],
                "fichier": SimpleUploadedFile("rapport.pdf", b"%PDF-1.4\nproof", content_type="application/pdf"),
                **values,
            },
            format="multipart",
        )
        if response.status_code < 300:
            self.project["version"] = response.data["version"]
        return response

    def draft(self, **overrides):
        return self.mutate(
            self.team_path("evaluations/"),
            self.evaluator,
            **{
                "jalon": self.milestone["id"],
                "note_groupe": "16.00",
                "commentaire": "Travail argumenté.",
                "contributions": [
                    {"membre": self.alice.pk, "note": "17.00", "commentaire": "Analyse solide."},
                    {"membre": self.anne.pk, "note": "15.00", "commentaire": "Prototype fonctionnel."},
                ],
                **overrides,
            },
        )

    def publish(self, evaluation, **kwargs):
        return self.mutate(self.team_path(f"evaluations/{evaluation['id']}/publier/"), self.evaluator, **kwargs)


class PedagogicalProjectTests(ProjectFixture):
    def test_owner_scoped_teacher_can_create_without_access_to_colleagues_projects_or_files(self):
        self.grant(self.staff, "gerer_projet_pedagogique")
        self.manager.attributs_acces = {
            "permission_scopes": {"core.gerer_projet_pedagogique": {"responsable_id": [self.manager.pk]}}
        }
        self.manager.save(update_fields=["attributs_acces"])
        self.evaluator.attributs_acces = {
            "permission_scopes": {"core.evaluer_projet_pedagogique": {"responsable_id": [self.manager.pk]}}
        }
        self.evaluator.save(update_fields=["attributs_acces"])
        self.other_evaluator.attributs_acces = {
            "permission_scopes": {"core.evaluer_projet_pedagogique": {"responsable_id": [self.staff.pk]}}
        }
        self.other_evaluator.save(update_fields=["attributs_acces"])
        self.login(self.manager)
        assert self.client.get(f"{BASE}capacites/").data["can_create"] is True
        candidates = f"{BASE}candidats/?q=project"
        owners = self.client.get(f"{candidates}&type=responsable")
        assert owners.status_code == 200, owners.data
        assert [owner["id"] for owner in owners.data["results"]] == [self.manager.pk]
        evaluators = self.client.get(f"{candidates}&type=evaluateur")
        assert evaluators.status_code == 200, evaluators.data
        evaluator_ids = {user["id"] for user in evaluators.data["results"]}
        assert self.evaluator.pk in evaluator_ids
        assert self.other_evaluator.pk not in evaluator_ids
        assert self.client.get(f"{candidates}&type=membre").status_code == 200
        for kind in ("responsable", "membre", "evaluateur"):
            assert self.client.get(f"{candidates}&type={kind}&responsable={self.staff.pk}").status_code == 403
        own = self.create_project()
        assert own["responsable"] == self.manager.pk
        assert own["actions"]["can_manage"] is True
        assert self.mutate("configurer/", titre="Mon projet scoped").status_code == 200

        self.login(self.staff)
        payload = {"titre": "Projet du collègue", "mode": "collectif", "responsable": self.staff.pk}
        colleague = self.client.post(BASE, payload, format="json")
        assert colleague.status_code == 201, colleague.data
        self.project = colleague.data
        milestone = self.mutate(
            "jalons/", self.staff, titre="Rapport", ordre=1, echeance="2030-01-01T00:00:00Z", bareme="20"
        )
        assert milestone.status_code == 201, milestone.data
        self.milestone = milestone.data["jalon"]
        team = self.mutate("equipes/", self.staff, nom="Équipe privée", membres=[self.bob.pk])
        assert team.status_code == 201, team.data
        self.team = team.data["equipe"]
        delivery = self.upload(self.bob)
        assert delivery.status_code == 201, delivery.data
        foreign_project_url = self.url()
        foreign_file_url = self.url(self.team_path(f"livrables/{delivery.data['livrable']['id']}/telecharger/"))
        self.login(self.manager)
        assert self.client.post(BASE, payload, format="json").status_code == 403
        assert self.client.get(foreign_project_url).status_code == 404
        assert (
            self.client.post(
                f"{foreign_project_url}configurer/",
                {"version": self.project["version"], "titre": "Intrusion"},
                format="json",
            ).status_code
            == 404
        )
        with patch.object(self.storage, "open", side_effect=AssertionError("Colleague file read")):
            assert self.client.get(foreign_file_url).status_code == 404
        assert [item["id"] for item in self.client.get(BASE).data["results"]] == [own["id"]]
        self.project = own
        assert self.mutate("configurer/", responsable=self.staff.pk).status_code == 403
        assert PedagogicalProject.objects.get(pk=own["id"]).responsable_id == self.manager.pk

        self.manager.attributs_acces = {
            "permission_scopes": {"core.gerer_projet_pedagogique": {"projet_id": [own["id"]]}}
        }
        self.manager.save(update_fields=["attributs_acces"])
        self.login(self.manager)
        assert self.client.get(f"{BASE}capacites/").data["can_create"] is False
        assert self.client.get(f"{candidates}&type=responsable").status_code == 403
        assert self.client.post(BASE, {**payload, "responsable": self.manager.pk}, format="json").status_code == 403

    def test_precreation_candidates_use_selected_eligible_owner_without_general_management(self):
        self.grant(self.staff, "gerer_projet_pedagogique")
        self.manager.attributs_acces = {
            "permission_scopes": {"core.gerer_projet_pedagogique": {"responsable_id": [self.staff.pk]}}
        }
        self.manager.save(update_fields=["attributs_acces"])
        self.evaluator.attributs_acces = {
            "permission_scopes": {"core.evaluer_projet_pedagogique": {"responsable_id": [self.staff.pk]}}
        }
        self.evaluator.save(update_fields=["attributs_acces"])
        self.login(self.manager)
        assert self.client.get(f"{BASE}capacites/").data["can_create"] is True
        candidates = f"{BASE}candidats/?q=project"
        owners = self.client.get(f"{candidates}&type=responsable")
        assert owners.status_code == 200, owners.data
        assert [owner["id"] for owner in owners.data["results"]] == [self.staff.pk]
        assert self.client.get(f"{candidates}&type=membre").status_code == 403
        assert self.client.get(f"{candidates}&type=evaluateur").status_code == 403
        members = self.client.get(f"{candidates}&type=membre&responsable={self.staff.pk}")
        assert members.status_code == 200, members.data
        evaluators = self.client.get(f"{candidates}&type=evaluateur&responsable={self.staff.pk}")
        assert evaluators.status_code == 200, evaluators.data
        assert self.evaluator.pk in {user["id"] for user in evaluators.data["results"]}
        response = self.client.post(
            BASE,
            {
                "titre": "Projet dans le périmètre délégué",
                "mode": "collectif",
                "responsable": self.staff.pk,
                "evaluateurs": [self.evaluator.pk],
            },
            format="json",
        )
        assert response.status_code == 201, response.data
        assert response.data["actions"]["can_manage"] is True
        assert (
            self.client.get(
                f"{candidates}&type=membre&responsable={self.staff.pk}&projet={response.data['id']}"
            ).status_code
            == 400
        )
        self.staff.etablissement = self.other_tenant()
        self.staff.save(update_fields=["etablissement"])
        self.login(self.manager)
        assert self.client.get(f"{BASE}capacites/").data["can_create"] is False
        assert (
            self.client.post(
                BASE, {"titre": "Hors tenant", "mode": "collectif", "responsable": self.staff.pk}, format="json"
            ).status_code
            == 400
        )

    def test_complete_collective_workflow_keeps_revisions_and_publishes_only_human_assessment(self):
        self.prepare()
        first = self.upload()
        assert first.status_code == 201, first.data
        first = first.data["livrable"]
        second = self.upload(self.anne)
        assert second.status_code == 201, second.data
        assert second.data["livrable"]["revision"] == 2
        assert ProjectDelivery.objects.count() == 2
        assert "fichier" not in second.data["livrable"]
        self.login(self.alice)
        download = self.client.get(self.url(self.team_path(f"livrables/{first['id']}/telecharger/")))
        assert download.status_code == 200
        assert b"".join(download.streaming_content) == b"%PDF-1.4\nproof"
        assert download["Cache-Control"] == "private, no-store"
        with self.assertRaises(SuspiciousFileOperation):
            ProjectDelivery.objects.get(pk=first["id"]).fichier.url

        draft = self.draft()
        assert draft.status_code == 201, draft.data
        evaluation = draft.data["evaluation"]
        assert evaluation["statut"] == "brouillon"
        self.login(self.alice)
        assert self.client.get(self.url(self.team_path("evaluations/"))).data["count"] == 0
        published = self.publish(evaluation)
        assert published.status_code == 200, published.data
        assert published.data["evaluation"]["statut"] == "publiee"
        assert published.data["evaluation"]["publie_par"] == self.evaluator.pk
        self.login(self.alice)
        results = self.client.get(self.url(self.team_path("evaluations/"))).data["results"]
        assert results[0]["bareme"] == "20.00"
        assert results[0]["note_groupe"] == "16.00"
        assert results[0]["contributions"] == [
            {"membre": self.alice.pk, "note": "17.00", "commentaire": "Analyse solide."}
        ]
        self.login(self.manager)
        history = self.client.get(self.url("historique/"))
        assert history.status_code == 200, history.data
        published_event = next(row for row in history.data["results"] if row["action"] == "projet_publication")
        assert published_event["acteur"] == self.evaluator.pk
        assert published_event["created_at"]
        assert self.publish(evaluation).status_code == 400
        revised = self.draft(note_groupe="18.00")
        assert revised.status_code == 201
        assert revised.data["evaluation"]["revision"] == 2
        self.login(self.alice)
        assert self.client.get(self.url(self.team_path("evaluations/"))).data["count"] == 1
        assert ProjectEvaluation.objects.get(pk=evaluation["id"]).note_groupe == 16

    def test_other_team_same_project_cannot_enumerate_or_read_files_and_membership_is_not_global(self):
        self.prepare()
        upload = self.upload()
        assert upload.status_code == 201
        file_url = self.url(self.team_path(f"livrables/{upload.data['livrable']['id']}/telecharger/"))
        self.login(self.bob)
        assert self.client.get(self.url()).status_code == 200
        teams = self.client.get(self.url("equipes/"))
        assert teams.data["count"] == 1
        assert teams.data["results"][0]["id"] == self.other_team["id"]
        for user in (self.bob, self.outsider, self.staff, self.other_evaluator):
            self.login(user)
            with patch.object(self.storage, "open", side_effect=AssertionError("Unauthorized content read")):
                assert self.client.get(file_url).status_code == 404
            assert self.client.get(self.url(self.team_path("livrables/"))).status_code == 404
            assert self.client.get(self.url(self.team_path("evaluations/"))).status_code == 404
            with patch(
                "rest_framework.parsers.MultiPartParser.parse", side_effect=AssertionError("Parsed private upload")
            ):
                assert self.upload(user).status_code == 404
        original = self.project
        self.create_project()
        hidden_url = self.url()
        self.project = original
        self.login(self.alice)
        listing = self.client.get(BASE)
        assert listing.data["count"] == 1
        assert self.client.get(hidden_url).status_code == 404
        assert self.client.get(self.url("historique/")).status_code == 403
        assert self.client.get(f"{BASE}candidats/?type=membre&q=project").status_code == 403

    def test_member_retirement_immediately_revokes_all_access_without_destroying_evidence(self):
        self.prepare()
        upload = self.upload()
        assert upload.status_code == 201
        delivery_id = upload.data["livrable"]["id"]
        response = self.mutate(self.team_path("membres/"), membres=[self.anne.pk])
        assert response.status_code == 200, response.data
        retired = ProjectMembership.objects.get(equipe_id=self.team["id"], membre=self.alice)
        assert retired.retired_at and retired.retire_par == self.manager
        self.login(self.alice)
        assert self.client.get(BASE).data["count"] == 0
        assert self.client.get(self.url()).status_code == 404
        with patch.object(self.storage, "open", side_effect=AssertionError("Retired member read")):
            assert self.client.get(self.url(self.team_path(f"livrables/{delivery_id}/telecharger/"))).status_code == 404
        assert self.upload().status_code == 404
        assert ProjectDelivery.objects.filter(pk=delivery_id).exists()
        restored = self.mutate(self.team_path("membres/"), membres=[self.alice.pk, self.anne.pk])
        assert restored.status_code == 200
        assert ProjectMembership.objects.filter(equipe_id=self.team["id"], membre=self.alice).count() == 2

    def test_disabled_module_blocks_every_api_and_file_then_reactivation_preserves_records(self):
        self.prepare()
        uploaded = self.upload().data["livrable"]
        draft = self.draft().data["evaluation"]
        before = (ProjectTeam.objects.count(), ProjectDelivery.objects.count(), ProjectEvaluation.objects.count())
        self.toggle(False)
        self.login(self.admin)
        get_paths = [
            BASE,
            self.url(),
            f"{BASE}capacites/",
            f"{BASE}candidats/?q=project&type=membre",
            self.url("equipes/"),
            self.url("jalons/"),
            self.url("historique/"),
            self.url(self.team_path("livrables/")),
            self.url(self.team_path("evaluations/")),
            self.url(self.team_path(f"livrables/{uploaded['id']}/telecharger/")),
        ]
        with patch.object(self.storage, "open", side_effect=AssertionError("Disabled module file read")):
            for url in get_paths:
                assert self.client.get(url).status_code == 403, url
        post_paths = [
            BASE,
            self.url("configurer/"),
            self.url("equipes/"),
            self.url("jalons/"),
            self.url(self.team_path("membres/")),
            self.url(self.team_path("livrables/")),
            self.url(self.team_path("evaluations/")),
            self.url(self.team_path(f"evaluations/{draft['id']}/publier/")),
        ]
        for url in post_paths:
            assert self.client.post(url, {}, format="json").status_code == 403, url
        self.toggle(True)
        self.login(self.alice)
        assert self.client.get(self.url()).status_code == 200
        response = self.client.get(self.url(self.team_path(f"livrables/{uploaded['id']}/telecharger/")))
        assert response.status_code == 200
        assert b"".join(response.streaming_content).startswith(b"%PDF-")
        assert before == (
            ProjectTeam.objects.count(),
            ProjectDelivery.objects.count(),
            ProjectEvaluation.objects.count(),
        )

    def test_individual_teams_and_foreign_key_commands_are_coherent_and_atomic(self):
        self.prepare("individuel")
        assert self.mutate("equipes/", nom="Invalide", membres=[self.anne.pk, self.outsider.pk]).status_code == 400
        assert not ProjectTeam.objects.filter(nom="Invalide").exists()
        assert self.mutate(self.team_path("membres/"), membres=[self.alice.pk, self.anne.pk]).status_code == 400
        assert self.mutate("equipes/", nom="Doublon", membres=[self.alice.pk]).status_code == 400
        assert self.mutate("equipes/", nom="Agent", membres=[self.staff.pk]).status_code == 400
        assert self.mutate("equipes/", nom="Absent", membres=[999999]).status_code == 400
        assert ProjectTeam.objects.count() == 2
        original, original_milestone, original_team = self.project, self.milestone, self.team
        self.prepare()
        foreign_milestone, foreign_team = self.milestone, self.team
        self.project, self.milestone, self.team = original, original_milestone, original_team
        assert self.upload(jalon=foreign_milestone["id"]).status_code == 404
        assert self.mutate(self.team_path("membres/", foreign_team), membres=[]).status_code == 404
        assert self.draft(jalon=foreign_milestone["id"], contributions=[]).status_code == 404
        assert (
            self.draft(contributions=[{"membre": self.bob.pk, "note": "10", "commentaire": "Autre équipe"}]).status_code
            == 400
        )
        assert ProjectDelivery.objects.count() == 0
        assert ProjectEvaluation.objects.count() == 0

    def test_scores_publication_and_membership_changes_require_new_complete_human_draft(self):
        self.prepare()
        for score in ("-0.01", "20.01", "NaN", "Infinity"):
            assert self.draft(note_groupe=score).status_code == 400
        assert (
            self.draft(
                contributions=[{"membre": self.alice.pk, "note": "20.01", "commentaire": "Hors barème"}]
            ).status_code
            == 400
        )
        assert (
            self.draft(
                contributions=[
                    {"membre": self.alice.pk, "note": "10", "commentaire": "A"},
                    {"membre": self.alice.pk, "note": "11", "commentaire": "B"},
                ]
            ).status_code
            == 400
        )
        partial = self.draft(contributions=[]).data["evaluation"]
        assert self.publish(partial).status_code == 400
        complete = self.draft(note_groupe="0.00").data["evaluation"]
        assert self.publish(partial).status_code == 400
        assert self.mutate(self.team_path("membres/"), membres=[self.alice.pk]).status_code == 200
        assert self.publish(complete).status_code == 400
        refreshed = self.draft(
            note_groupe="20.00",
            contributions=[{"membre": self.alice.pk, "note": "0.00", "commentaire": "Présence seule"}],
        ).data["evaluation"]
        assert self.publish(refreshed).status_code == 200
        assert ProjectEvaluation.objects.filter(published_at__isnull=False).count() == 1

    def test_permissions_are_not_staff_roles_membership_or_unassigned_evaluator_flags(self):
        self.prepare()
        draft = self.draft().data["evaluation"]
        for user in (self.alice, self.staff, self.other_evaluator):
            self.login(user)
            assert (
                self.client.post(
                    BASE, {"titre": "Intrusion", "mode": "collectif", "responsable": user.pk}, format="json"
                ).status_code
                == 403
            )
        for user in (self.alice, self.staff, self.other_evaluator):
            expected = 403 if user == self.alice else 404
            assert self.mutate("configurer/", user, responsable=user.pk).status_code == expected
            assert self.mutate(self.team_path("membres/"), user, membres=[user.pk]).status_code == expected
            assert self.mutate(self.team_path(f"evaluations/{draft['id']}/publier/"), user).status_code == expected
        assert (
            self.mutate(
                self.team_path("evaluations/"),
                self.manager,
                jalon=self.milestone["id"],
                note_groupe="20",
                commentaire="Non habilité",
                contributions=[],
            ).status_code
            == 403
        )
        self.grant(self.alice, "gerer_projet_pedagogique")
        self.grant(self.alice, "evaluer_projet_pedagogique")
        assert self.mutate("configurer/", self.alice, titre="Intrusion").status_code == 403
        self.login(self.manager)
        for method in (self.client.patch, self.client.put, self.client.delete):
            assert method(self.url(), {"responsable": self.alice.pk}, format="json").status_code == 405
        assert self.mutate("configurer/", mode="individuel").status_code == 400
        assert (
            self.mutate("equipes/", nom="Surpost", membres=[self.outsider.pk], projet=str(uuid4())).status_code == 400
        )
        assert self.draft(statut="publiee").status_code == 400

    def test_abac_scopes_are_applied_to_lists_delegation_evaluation_and_file_access(self):
        self.prepare()
        delivery = self.upload().data["livrable"]
        project_id = self.project["id"]
        self.manager.attributs_acces = {
            "permission_scopes": {"core.gerer_projet_pedagogique": {"projet_id": [project_id]}}
        }
        self.manager.save(update_fields=["attributs_acces"])
        self.login(self.manager)
        assert self.client.get(BASE).data["count"] == 1
        assert self.client.get(f"{BASE}capacites/").data["can_create"] is False
        assert self.mutate("configurer/", titre="Projet borné").status_code == 200
        for permission_user, permission in (
            (self.manager, "core.gerer_projet_pedagogique"),
            (self.evaluator, "core.evaluer_projet_pedagogique"),
        ):
            for constraints in ({"projet_id": [str(uuid4())]}, {"unknown_scope": [1]}, {"etablissement_id": [-1]}):
                permission_user.attributs_acces = {"permission_scopes": {permission: constraints}}
                permission_user.save(update_fields=["attributs_acces"])
                self.login(permission_user)
                assert self.client.get(BASE).data["count"] == 0
                assert self.client.get(self.url()).status_code == 404
                with patch.object(self.storage, "open", side_effect=AssertionError("Out-of-scope file read")):
                    assert (
                        self.client.get(
                            self.url(self.team_path(f"livrables/{delivery['id']}/telecharger/"))
                        ).status_code
                        == 404
                    )
        self.manager.attributs_acces = {
            "permission_scopes": {"core.gerer_projet_pedagogique": {"responsable_id": [self.manager.pk]}}
        }
        self.manager.save(update_fields=["attributs_acces"])
        self.grant(self.staff, "gerer_projet_pedagogique")
        assert self.mutate("configurer/", responsable=self.staff.pk, evaluateurs=[]).status_code == 403
        assert PedagogicalProject.objects.get(pk=project_id).responsable_id == self.manager.pk
        self.manager.attributs_acces = {}
        self.manager.save(update_fields=["attributs_acces"])
        assert self.mutate("configurer/", evaluateurs=[self.evaluator.pk]).status_code == 400

    def other_tenant(self):
        other = type(self.tenant)(
            schema_name="projects_other",
            nom="Autre établissement",
            type=self.tenant.type,
            adresse=self.tenant.adresse,
            code_postal=self.tenant.code_postal,
            ville=self.tenant.ville,
            telephone=self.tenant.telephone,
            email="projects-other@example.test",
        )
        other.auto_create_schema = False
        with schema_context("public"):
            other.save()
        return other

    def test_foreign_tenant_user_and_foreign_relations_are_rejected_before_content_read(self):
        self.prepare()
        uploaded = self.upload().data["livrable"]
        other = self.other_tenant()
        self.staff.etablissement = other
        self.staff.save(update_fields=["etablissement"])
        self.grant(self.staff, "gerer_projet_pedagogique")
        self.grant(self.staff, "evaluer_projet_pedagogique")
        self.login(self.staff)
        with patch.object(self.storage, "open", side_effect=AssertionError("Foreign file read")):
            assert self.client.get(BASE).status_code == 403
            assert (
                self.client.get(self.url(self.team_path(f"livrables/{uploaded['id']}/telecharger/"))).status_code == 403
            )
        with patch("rest_framework.parsers.MultiPartParser.parse", side_effect=AssertionError("Foreign upload parsed")):
            assert self.upload(self.staff).status_code == 403
        assert self.mutate("configurer/", responsable=self.staff.pk).status_code == 400
        assert self.mutate("configurer/", evaluateurs=[self.staff.pk]).status_code == 400
        self.bob.etablissement = other
        self.bob.save(update_fields=["etablissement"])
        assert self.mutate(self.team_path("membres/"), membres=[self.alice.pk, self.bob.pk]).status_code == 400
        PedagogicalProject.objects.filter(pk=self.project["id"]).update(etablissement=other)
        for user in (self.manager, self.evaluator, self.alice):
            self.login(user)
            assert self.client.get(BASE).data["count"] == 0
            assert self.client.get(self.url()).status_code == 404

    def test_revoked_evaluator_and_reassignment_remove_access_immediately(self):
        self.prepare()
        assert self.mutate("configurer/", evaluateurs=[self.other_evaluator.pk]).status_code == 200
        self.login(self.evaluator)
        assert self.client.get(self.url()).status_code == 404
        self.other_evaluator.user_permissions.clear()
        self.login(self.other_evaluator)
        assert self.client.get(self.url()).status_code == 404
        self.grant(self.staff, "gerer_projet_pedagogique")
        assert self.mutate("configurer/", responsable=self.staff.pk, evaluateurs=[]).status_code == 200
        self.manager.user_permissions.clear()
        self.login(self.manager)
        assert self.client.get(self.url()).status_code == 404

    def test_conflicts_and_audit_failures_roll_back_memberships_evaluations_and_uploads(self):
        self.prepare()
        version = self.project["version"]
        assert self.mutate("configurer/", titre="Révision").status_code == 200
        assert self.mutate(self.team_path("membres/"), version=version, membres=[]).status_code == 409
        assert ProjectMembership.objects.filter(equipe_id=self.team["id"], retired_at__isnull=True).count() == 2
        current = self.project["version"]
        before = WorkflowEvent.objects.filter(model="pedagogicalproject").count()
        with patch("sis_common.projects.record_workflow_event", side_effect=RuntimeError("Audit unavailable")):
            assert self.mutate(self.team_path("membres/"), membres=[self.bob.pk]).status_code == 400
        with patch("sis_common.projects.record_workflow_event", side_effect=RuntimeError("Audit unavailable")):
            with self.assertRaises(RuntimeError):
                self.mutate(self.team_path("membres/"), membres=[self.alice.pk, self.outsider.pk])
            with self.assertRaises(RuntimeError):
                self.draft()
            with self.assertRaises(RuntimeError):
                self.upload()
        assert ProjectMembership.objects.filter(equipe_id=self.team["id"], retired_at__isnull=True).count() == 2
        assert not ProjectMembership.objects.filter(membre=self.outsider).exists()
        assert ProjectEvaluation.objects.count() == 0
        assert ProjectContribution.objects.count() == 0
        assert ProjectDelivery.objects.count() == 0
        assert not list(self.storage_folder.rglob("*.pdf"))
        assert PedagogicalProject.objects.get(pk=self.project["id"]).version == current
        assert WorkflowEvent.objects.filter(model="pedagogicalproject").count() == before
        draft = self.draft().data["evaluation"]
        with patch("sis_common.projects.record_workflow_event", side_effect=RuntimeError("Audit unavailable")):
            with self.assertRaises(RuntimeError):
                self.publish(draft)
        assert ProjectEvaluation.objects.get(pk=draft["id"]).published_at is None

    def test_upload_validation_and_private_history_do_not_leak_through_generic_audit(self):
        self.prepare()
        for name, body, mime in (
            ("rapport.exe", b"%PDF-1.4", "application/pdf"),
            ("rapport.pdf", b"not a PDF", "application/pdf"),
            ("rapport.pdf", b"%PDF-1.4", "text/html"),
        ):
            assert self.upload(fichier=SimpleUploadedFile(name, body, content_type=mime)).status_code == 400
        with override_settings(EXAM_COPY_MAX_SIZE=5):
            assert self.upload().status_code == 400
        assert ProjectDelivery.objects.count() == 0
        assert not list(self.storage_folder.rglob("*.pdf"))
        upload = self.upload(
            fichier=SimpleUploadedFile("../../rapport à relire.pdf", b"%PDF-1.4", content_type="application/pdf")
        )
        assert upload.status_code == 201, upload.data
        assert "/" not in upload.data["livrable"]["nom"]
        assert "\\" not in upload.data["livrable"]["nom"]
        self.grant(self.staff, "view_workflowevent")
        self.login(self.staff)
        response = self.client.get("/api/v1/core/workflow-events/?model=pedagogicalproject")
        assert response.status_code == 200, response.data
        assert response.data["count"] == 0
        self.login(self.manager)
        assert self.client.get(BASE + "?mode=inconnu").status_code == 400
        assert self.client.get(self.url(self.team_path("livrables/?jalon=invalide"))).status_code == 400
        assert (
            self.mutate(
                "jalons/", titre="Sans échelle", ordre=2, echeance="2030-01-01T00:00:00Z", bareme="0"
            ).status_code
            == 400
        )
        assert ProjectMilestone.objects.count() == 1

    def test_scoped_participant_selector_and_resource_capabilities_need_no_global_user_permission(self):
        self.prepare()
        self.manager.attributs_acces = {
            "permission_scopes": {"core.gerer_projet_pedagogique": {"projet_id": [self.project["id"]]}}
        }
        self.manager.save(update_fields=["attributs_acces"])
        self.login(self.manager)
        assert not self.manager.has_perm("utilisateurs.view_utilisateur")
        assert self.client.get(f"{BASE}capacites/").data["can_create"] is False
        candidates = f"{BASE}candidats/?projet={self.project['id']}&q=project&type=membre"
        response = self.client.get(candidates)
        assert response.status_code == 200, response.data
        assert {item["id"] for item in response.data["results"]} == {
            self.alice.pk,
            self.anne.pk,
            self.bob.pk,
            self.outsider.pk,
        }
        assert all(set(item) == {"id", "nom"} for item in response.data["results"])
        assert self.client.get(f"{BASE}candidats/?q=project&type=membre").status_code == 403
        assert self.client.get(candidates.replace(self.project["id"], str(uuid4()))).status_code == 404
        project = self.client.get(self.url()).data
        assert project["actions"] == {"can_manage": True, "can_submit": False, "can_evaluate": False}
        self.login(self.evaluator)
        assert self.client.get(candidates).status_code == 403
        assert self.client.get(self.url()).data["actions"]["can_evaluate"] is True
        self.login(self.alice)
        assert self.client.get(candidates).status_code == 403
        teams = self.client.get(self.url("equipes/"))
        assert teams.data["results"][0]["actions"] == {
            "can_manage": False,
            "can_submit": True,
            "can_evaluate": False,
        }
        self.login(self.manager)
        invalid = self.client.post(self.url("configurer/"), [{"titre": "Lot interdit"}], format="json")
        assert invalid.status_code == 400


class ProjectConcurrencyTests(ProjectFixture):
    @classmethod
    def _fixture_setup(cls):
        TransactionTestCase._fixture_setup.__func__(cls)

    def _fixture_teardown(self):
        with schema_context(self.tenant.schema_name):
            TransactionTestCase._fixture_teardown(self)

    def test_publication_and_membership_change_serialize_with_one_version_and_atomic_audit(self):
        assert not connection.in_atomic_block
        self.prepare()
        evaluation = self.draft().data["evaluation"]
        version = self.project["version"]
        before = WorkflowEvent.objects.filter(model="pedagogicalproject").count()
        barrier = Barrier(2)
        requests = [
            (
                self.manager.pk,
                self.url(self.team_path("membres/")),
                {"version": version, "membres": [self.alice.pk]},
            ),
            (
                self.evaluator.pk,
                self.url(self.team_path(f"evaluations/{evaluation['id']}/publier/")),
                {"version": version},
            ),
        ]

        def mutate(command):
            actor_id, url, payload = command
            try:
                with schema_context(self.tenant.schema_name):
                    actor = get_user_model().objects.get(pk=actor_id)
                    client = APIClient(SERVER_NAME=self.get_test_tenant_domain())
                    client.force_authenticate(actor)
                    barrier.wait(timeout=10)
                    response = client.post(url, payload, format="json")
                    return response.status_code
            finally:
                connections["default"].close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(mutate, requests))
        assert sorted(results) == [200, 409]
        assert PedagogicalProject.objects.get(pk=self.project["id"]).version == version + 1
        assert WorkflowEvent.objects.filter(model="pedagogicalproject").count() == before + 1
        published = ProjectEvaluation.objects.get(pk=evaluation["id"]).published_at is not None
        member_count = ProjectMembership.objects.filter(equipe_id=self.team["id"], retired_at__isnull=True).count()
        assert (published, member_count) == ((False, 1) if results[0] == 200 else (True, 2))
        assert ProjectContribution.objects.count() == 2
