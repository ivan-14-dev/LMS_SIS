"""Mounted project/course commands on real tenant SQL tables, for both SIS variants."""

from copy import deepcopy
from unittest.mock import patch
from uuid import uuid4

from apps.core.models import PedagogicalProject, ProjectContribution, WorkflowEvent
from apps.integration.models import EdxAccessIntent, EdxCourseMapping, EdxEnrollment, OutboxEvent
from apps.notes.models import Note
from django.conf import settings
from django.contrib.auth.models import Permission
from django.db import transaction
from django.db.models.deletion import ProtectedError
from django_tenants.utils import schema_context

from sis_common.tests.test_projects import BASE, ProjectFixture

MANAGE = "core.gerer_projet_pedagogique"
READ = "integration.view_edxcoursemapping"


class ProjectCourseTests(ProjectFixture):
    def setUp(self):
        super().setUp()
        self.course_permission = Permission.objects.get(
            content_type__app_label="integration", codename="view_edxcoursemapping"
        )
        self.course_access(self.manager)
        self.grant(self.staff, "gerer_projet_pedagogique")
        self.course_access(self.staff)
        self.course = self.make_course("A", self.tenant)
        self.alternative = self.make_course("B", self.tenant)

    def course_access(self, user):
        user.is_staff = True
        user.save(update_fields=["is_staff"])
        user.user_permissions.add(self.course_permission)

    def make_course(self, code, tenant, active=True):
        if settings.SIS_VARIANT == "secondaire":
            from apps.classes.models import Classe, Matiere
            from apps.etablissement.models import AnneeScolaire, Niveau

            year = AnneeScolaire.objects.create(
                etablissement=tenant, libelle=f"Année {code}", date_debut="2026-09-01", date_fin="2027-08-31"
            )
            level = Niveau.objects.create(etablissement=tenant, code=code, libelle=f"Niveau {code}")
            classroom = Classe.objects.create(
                etablissement=tenant, annee_scolaire=year, niveau=level, nom=f"Classe {code}"
            )
            subject = Matiere.objects.create(etablissement=tenant, code=code, nom=f"Matière {code}")
            context = {"classe": classroom, "matiere": subject}
        else:
            from apps.etablissement.models import AnneeUniversitaire, Semestre
            from apps.formations.models import Formation, MaquetteFormation
            from apps.ue_ecue.models import ECUE, UE

            year = AnneeUniversitaire.objects.create(
                universite=tenant, libelle=f"Année {code}", date_debut="2026-09-01", date_fin="2027-08-31"
            )
            semester = Semestre.objects.create(
                annee_universitaire=year, numero=1, type="impair", date_debut="2026-09-01", date_fin="2027-01-31"
            )
            formation = Formation.objects.create(code=code, nom=f"Formation {code}", type="licence")
            curriculum = MaquetteFormation.objects.create(formation=formation, annee_universitaire=year)
            unit = UE.objects.create(
                code=code, nom=f"UE {code}", maquette=curriculum, semestre=semester, credits_ects=6
            )
            ecue = ECUE.objects.create(ue=unit, code=code, nom=f"ECUE {code}", credits_ects=3)
            context = {"ecue": ecue}
        return EdxCourseMapping.objects.create(
            **context, course_id=f"course-v1:SIS+PROJECT-{code}+sis", course_name=f"Cours projet {code}", actif=active
        )

    def scopes(self, user, **permissions):
        user.attributs_acces = {"permission_scopes": permissions}
        user.save(update_fields=["attributs_acces"])

    def search(self, user=None, owner=None, **params):
        self.login(user or self.manager)
        return self.client.get(
            f"{BASE}cours-candidats/",
            {"q": "cours projet", "responsable": (owner or self.manager).pk, **params},
        )

    def create_bound(self, owner=None, course=None):
        self.login(self.manager)
        response = self.client.post(
            BASE,
            {
                "titre": "Projet rattaché",
                "mode": "collectif",
                "responsable": (owner or self.manager).pk,
                "cours": (course or self.course).pk,
            },
            format="json",
        )
        if response.status_code == 201:
            self.project = response.data
        return response

    def events(self):
        return WorkflowEvent.objects.filter(model="pedagogicalproject").order_by("pk")

    def test_create_replace_clear_and_protect_mapping_without_any_lms_or_grade_effect(self):
        models = [EdxCourseMapping, EdxEnrollment, EdxAccessIntent, OutboxEvent, Note]
        before = [list(model.objects.order_by("pk").values()) for model in models]
        with (
            patch("apps.integration.api.get_edx_client") as remote,
            patch("apps.integration.api.SyncService") as service,
        ):
            response = self.create_bound()
            assert response.status_code == 201, response.data
            assert response.data["cours"]["id"] == self.course.pk
            context = response.data["cours"]["contexte"]
            assert set(context) == ({"classe", "matiere"} if settings.SIS_VARIANT == "secondaire" else {"ecue"})
            assert "course_id" not in response.data["cours"]
            with self.assertRaises(ProtectedError):
                self.course.delete()
            replacement = self.mutate("configurer/", cours=self.alternative.pk)
            assert replacement.status_code == 200, replacement.data
            assert replacement.data["cours"]["id"] == self.alternative.pk
            cleared = self.mutate("configurer/", cours=None)
            assert cleared.status_code == 200, cleared.data
            assert cleared.data["cours"] is None
            remote.assert_not_called()
            service.assert_not_called()
        assert [list(model.objects.order_by("pk").values()) for model in models] == before
        events = list(self.events())
        assert events[0].metadata["cours"]["id"] == self.course.pk
        assert events[1].metadata["avant"]["cours"] == events[0].metadata["cours"]
        assert events[1].metadata["cours"]["id"] == self.alternative.pk
        assert events[2].metadata["avant"]["cours"] == events[1].metadata["cours"]
        assert events[2].metadata["cours"] is None
        assert [event.metadata["version"] for event in events] == [1, 2, 3]

    def test_unbound_project_stays_usable_without_course_permissions_or_staff(self):
        self.manager.user_permissions.remove(self.course_permission)
        self.manager.is_staff = False
        self.manager.save(update_fields=["is_staff"])
        self.scopes(self.manager, **{MANAGE: {"responsable_id": [self.manager.pk]}})
        self.prepare()
        assert self.project["cours"] is None
        assert self.mutate("configurer/", titre="Toujours sans cours").status_code == 200
        assert self.upload().status_code == 201
        assert self.search().data["results"] == []
        assert self.create_bound().status_code == 400

    def test_candidates_intersect_both_scoped_accounts_and_selected_owner_without_directory_permission(self):
        self.scopes(
            self.manager,
            **{MANAGE: {"responsable_id": [self.staff.pk]}, READ: {"cours": [self.course.pk, self.alternative.pk]}},
        )
        self.scopes(self.staff, **{MANAGE: {"responsable_id": [self.staff.pk]}, READ: {"cours": [self.course.pk]}})
        result = self.search(owner=self.staff)
        assert result.status_code == 200, result.data
        assert [row["id"] for row in result.data["results"]] == [self.course.pk]
        assert not self.manager.has_perm("utilisateurs.view_utilisateur")
        assert self.create_bound(self.staff, self.alternative).status_code == 400
        bound = self.create_bound(self.staff)
        assert bound.status_code == 201, bound.data
        self.scopes(self.manager, **{MANAGE: {"projet_id": [bound.data["id"]]}, READ: {"cours": [self.course.pk]}})
        result = self.search(owner=self.staff, projet=bound.data["id"])
        assert result.status_code == 200, result.data
        assert [row["id"] for row in result.data["results"]] == [self.course.pk]
        assert self.search(owner=self.staff).status_code == 403
        assert self.mutate("configurer/", cours=self.course.pk).status_code == 200
        self.scopes(self.manager, **{MANAGE: {"projet_id": [bound.data["id"]]}, READ: {"cours": []}})
        assert self.search(owner=self.staff, projet=bound.data["id"]).data["results"] == []
        assert self.mutate("configurer/", cours=self.course.pk).status_code == 400

    def test_search_is_bounded_paginated_and_never_uses_an_unrestricted_catalogue(self):
        first = self.search(page_size=1)
        assert first.status_code == 200, first.data
        assert first.data["count"] == 2 and len(first.data["results"]) == 1
        assert first.data["next"] and first.data["previous"] is None
        second = self.search(page_size=1, page=2)
        assert second.data["results"][0]["id"] != first.data["results"][0]["id"]
        assert second.data["next"] is None and second.data["previous"]
        assert self.search(q="COURSE-V1:SIS+PROJECT-B").data["results"][0]["id"] == self.alternative.pk
        for term in ("", "a", "x" * 101, "cours\nprojet"):
            assert self.search(q=term).status_code == 400
        for scopes in ({"inconnu": [1]}, {"cours": "all"}, {"cours": ["bad"]}, {"cours": []}):
            self.scopes(self.manager, **{READ: scopes})
            assert self.search().data["count"] == 0
            assert self.create_bound().status_code == 400

    def test_academic_scopes_reuse_native_course_context_including_both_university_years(self):
        if settings.SIS_VARIANT == "secondaire":
            scopes = {
                "classes": [self.course.classe_id],
                "matieres": [self.course.matiere_id],
                "annees": [self.course.classe.annee_scolaire_id],
            }
        else:
            scopes = {
                "ecues": [self.course.ecue_id],
                "formations": [self.course.ecue.ue.maquette.formation_id],
                "annees": [self.course.ecue.ue.semestre.annee_universitaire_id],
            }
        self.scopes(self.manager, **{READ: scopes})
        assert [row["id"] for row in self.search().data["results"]] == [self.course.pk]
        assert self.create_bound().status_code == 201
        if settings.SIS_VARIANT == "secondaire":
            self.course.classe.annee_scolaire = self.alternative.classe.annee_scolaire
            self.course.classe.save(update_fields=["annee_scolaire"])
        else:
            self.course.ecue.ue.maquette.annee_universitaire = self.alternative.ecue.ue.semestre.annee_universitaire
            self.course.ecue.ue.maquette.save(update_fields=["annee_universitaire"])
        assert self.search().data["results"] == []
        assert self.mutate("configurer/", titre="Refus année hors scope").status_code == 400

    def rename_course_labels(self):
        EdxCourseMapping.objects.filter(pk=self.course.pk).update(course_name="Cours projet nouveau périmètre")
        if settings.SIS_VARIANT == "secondaire":
            classroom, subject = self.course.classe, self.course.matiere
            type(classroom).objects.filter(pk=classroom.pk).update(nom="Classe nouveau périmètre")
            type(subject).objects.filter(pk=subject.pk).update(nom="Matière nouveau périmètre")
        else:
            ecue = self.course.ecue
            type(ecue).objects.filter(pk=ecue.pk).update(code="NEW-SCOPE", nom="ECUE nouveau périmètre")
        self.course.refresh_from_db()

    def move_course_context(self, change):
        if settings.SIS_VARIANT == "secondaire":
            classroom = self.course.classe
            field = "annee_scolaire" if change == "year" else "niveau"
            setattr(classroom, field, getattr(self.alternative.classe, field))
            classroom.save(update_fields=[field])
        else:
            ecue = self.course.ecue
            unit, alternative_unit = ecue.ue, self.alternative.ecue.ue
            if change == "ue":
                ecue.ue = alternative_unit
                ecue.save(update_fields=["ue"])
            elif change == "formation":
                unit.maquette.formation = alternative_unit.maquette.formation
                unit.maquette.save(update_fields=["formation"])
            else:
                if change in ("maquette_year", "both_years"):
                    unit.maquette.annee_universitaire = alternative_unit.maquette.annee_universitaire
                    unit.maquette.save(update_fields=["annee_universitaire"])
                if change in ("semestre_year", "both_years"):
                    unit.semestre.annee_universitaire = alternative_unit.semestre.annee_universitaire
                    unit.semestre.numero = 2
                    unit.semestre.type = "pair"
                    unit.semestre.save(update_fields=["annee_universitaire", "numero", "type"])
        self.rename_course_labels()

    def current_course_scope(self):
        if settings.SIS_VARIANT == "secondaire":
            return {
                "cours": [self.course.pk],
                "classes": [self.course.classe_id],
                "matieres": [self.course.matiere_id],
                "annees": [self.course.classe.annee_scolaire_id],
            }
        unit = self.course.ecue.ue
        return {
            "cours": [self.course.pk],
            "ecues": [self.course.ecue_id],
            "formations": [unit.maquette.formation_id],
            "annees": sorted({unit.maquette.annee_universitaire_id, unit.semestre.annee_universitaire_id}),
        }

    def test_history_hides_old_labels_after_scope_moves_even_when_course_and_context_ids_stay(self):
        changes = (
            ("year", "level")
            if settings.SIS_VARIANT == "secondaire"
            else ("ue", "formation", "maquette_year", "semestre_year", "both_years")
        )
        for change in changes:
            with self.subTest(change=change), transaction.atomic():
                self.course.refresh_from_db()
                assert self.create_bound().status_code == 201
                assert self.mutate("configurer/", titre="Confirmation historique").status_code == 200
                persisted = list(self.events().values())
                original = deepcopy(persisted[0]["metadata"]["cours"])
                self.move_course_context(change)
                self.scopes(
                    self.manager,
                    **{MANAGE: {"projet_id": [self.project["id"]]}, READ: self.current_course_scope()},
                )
                self.login(self.manager)
                current = self.client.get(self.url())
                assert current.status_code == 200, current.data
                assert current.data["cours"]["id"] == original["id"]
                assert current.data["cours"]["disponible"] is True
                assert current.data["cours"]["nom"] == "Cours projet nouveau périmètre"
                for key, context in original["contexte"].items():
                    assert current.data["cours"]["contexte"][key]["id"] == context["id"]
                choices = self.search(projet=self.project["id"])
                assert choices.status_code == 200, choices.data
                assert [row["id"] for row in choices.data["results"]] == [self.course.pk]
                history = self.client.get(self.url("historique/"))
                assert history.status_code == 200, history.data
                assert original["nom"] not in str(history.data)
                for context in original["contexte"].values():
                    assert context["nom"] not in str(history.data)
                for event in history.data["results"]:
                    assert event["metadata"]["cours"] == {"disponible": False}
                    if "avant" in event["metadata"]:
                        assert event["metadata"]["avant"]["cours"] == {"disponible": False}
                assert "_scope_fingerprint" not in str(history.data)
                assert list(self.events().values()) == persisted
                transaction.set_rollback(True)

    def test_renames_in_same_scope_keep_historical_names_but_never_expose_internal_fingerprints(self):
        assert self.create_bound().status_code == 201
        assert self.mutate("configurer/", titre="Confirmation historique").status_code == 200
        persisted = list(self.events().values())
        original = deepcopy(persisted[0]["metadata"]["cours"])
        fingerprint = original.pop("_scope_fingerprint")
        self.rename_course_labels()
        self.login(self.manager)
        history = self.client.get(self.url("historique/"))
        detail = self.client.get(self.url())
        choices = self.search()
        assert history.status_code == detail.status_code == choices.status_code == 200
        assert detail.data["cours"]["nom"] == "Cours projet nouveau périmètre"
        for event in history.data["results"]:
            assert event["metadata"]["cours"] == {**original, "disponible": True}
            if "avant" in event["metadata"]:
                assert event["metadata"]["avant"]["cours"] == {**original, "disponible": True}
        assert set(detail.data["cours"]) == {"id", "nom", "contexte", "disponible"}
        assert all(set(course) == {"id", "nom", "contexte"} for course in choices.data["results"])
        for result in (history, detail, choices):
            assert "_scope_fingerprint" not in str(result.data)
            assert fingerprint["sha256"] not in str(result.data)
        assert list(self.events().values()) == persisted

    def test_legacy_or_unknown_fingerprint_is_hidden_without_rewriting_persisted_evidence(self):
        assert self.create_bound().status_code == 201
        assert self.mutate("configurer/", titre="Confirmation historique").status_code == 200
        for event in self.events():
            metadata = deepcopy(event.metadata)
            for container in (metadata, metadata.get("avant", {})):
                snapshot = container.get("cours")
                if snapshot:
                    if event.action == "projet_creation":
                        snapshot.pop("_scope_fingerprint")
                    else:
                        snapshot["_scope_fingerprint"]["version"] = 999
            WorkflowEvent.objects.filter(pk=event.pk).update(metadata=metadata)
        persisted = list(self.events().values())
        self.login(self.manager)
        history = self.client.get(self.url("historique/"))
        assert history.status_code == 200, history.data
        assert self.course.course_name not in str(history.data)
        for event in history.data["results"]:
            assert event["metadata"]["cours"] == {"disponible": False}
            if "avant" in event["metadata"]:
                assert event["metadata"]["avant"]["cours"] == {"disponible": False}
        assert "_scope_fingerprint" not in str(history.data)
        assert list(self.events().values()) == persisted
        assert self.client.get(self.url()).data["cours"]["disponible"] is True

    def test_foreign_mixed_context_inactive_and_student_attempts_are_denied_without_audit(self):
        other = type(self.tenant)(schema_name=f"project_course_{uuid4().hex[:12]}")
        self.setup_tenant(other)
        other.auto_create_schema = False
        with schema_context("public"):
            other.save()
        foreign = self.make_course("FOREIGN", other)
        inactive = self.make_course("INACTIVE", self.tenant, active=False)
        mixed = self.make_course("MIXED", self.tenant)
        if settings.SIS_VARIANT == "secondaire":
            mixed.classe.niveau = foreign.classe.niveau
            mixed.classe.save(update_fields=["niveau"])
        else:
            mixed.ecue.ue.maquette = foreign.ecue.ue.maquette
            mixed.ecue.ue.save(update_fields=["maquette"])
        assert self.search().data["count"] == 2
        before = self.events().count()
        for course in (foreign, inactive, mixed):
            denied = self.create_bound(course=course)
            assert denied.status_code == 400, denied.data
            assert course.course_name not in str(denied.data)
        self.grant(self.alice, "gerer_projet_pedagogique")
        self.course_access(self.alice)
        assert self.search(user=self.alice).status_code == 403
        foreign_user = self.user("foreign-course-agent", "enseignant", is_staff=True, is_superuser=True)
        foreign_user.etablissement = other
        foreign_user.save(update_fields=["etablissement"])
        assert self.search(user=foreign_user).status_code == 403
        assert self.events().count() == before
        assert not PedagogicalProject.objects.exists()

    def test_owner_change_requires_course_compatibility_and_explicit_clear_is_possible(self):
        assert self.create_bound().status_code == 201
        self.scopes(self.staff, **{READ: {"cours": [self.alternative.pk]}})
        before = list(self.events().values())
        refused = self.mutate("configurer/", responsable=self.staff.pk, titre="Ne pas enregistrer")
        assert refused.status_code == 400, refused.data
        assert list(self.events().values()) == before
        current = PedagogicalProject.objects.get(pk=self.project["id"])
        assert current.responsable_id == self.manager.pk and current.titre == "Projet rattaché"
        assert self.search(owner=self.staff, projet=self.project["id"]).data["results"][0]["id"] == self.alternative.pk
        success = self.mutate("configurer/", responsable=self.staff.pk, cours=self.alternative.pk)
        assert success.status_code == 200, success.data
        assert success.data["responsable"] == self.staff.pk
        self.staff.user_permissions.remove(self.course_permission)
        assert self.mutate("configurer/", titre="Incompatible").status_code == 400
        assert self.mutate("configurer/", cours=None).status_code == 200

    def test_course_revocation_redacts_reads_but_keeps_binding_evidence_and_unrelated_work(self):
        self.prepare()
        assert self.mutate("configurer/", cours=self.course.pk).status_code == 200
        assert self.upload().status_code == 201
        draft = self.draft()
        assert draft.status_code == 201, draft.data
        evaluation = draft.data["evaluation"]
        assert self.publish(evaluation).status_code == 200
        proof = list(ProjectContribution.objects.order_by("pk").values())
        self.login(self.alice)
        assert self.client.get(self.url()).data["cours"] == {"disponible": False}
        self.login(self.manager)
        assert self.client.get(self.url()).data["cours"]["disponible"] is True
        EdxCourseMapping.objects.filter(pk=self.course.pk).update(actif=False)
        before = list(self.events().values())
        assert self.search().data["count"] == 1
        assert self.client.get(self.url()).data["cours"] == {"disponible": False}
        assert self.mutate("configurer/", titre="Refusée").status_code == 400
        assert list(self.events().values()) == before
        assert PedagogicalProject.objects.get(pk=self.project["id"]).cours_id == self.course.pk
        history = self.client.get(self.url("historique/"))
        assert history.status_code == 200
        assert self.course.course_name not in str(history.data)
        assert self.upload().status_code == 201
        assert self.mutate("configurer/", cours=None).status_code == 200
        assert list(ProjectContribution.objects.order_by("pk").values()) == proof
        evaluation_events = self.events().filter(action="projet_evaluation")
        assert evaluation_events.get().metadata["cours"]["id"] == self.course.pk
        assert evaluation_events.get().metadata["cours"]["nom"] == self.course.course_name

    def test_permission_and_staff_revocation_fail_closed_without_removing_project_access(self):
        assert self.create_bound().status_code == 201
        self.manager.user_permissions.remove(self.course_permission)
        assert self.search().data["results"] == []
        self.login(self.manager)
        assert self.client.get(self.url()).status_code == 200
        assert self.client.get(self.url()).data["cours"] == {"disponible": False}
        assert self.mutate("configurer/", cours=self.course.pk).status_code == 400
        assert self.course.course_name not in str(self.client.get(self.url("historique/")).data)
        self.manager.user_permissions.add(self.course_permission)
        self.manager.is_staff = False
        self.manager.save(update_fields=["is_staff"])
        assert self.search().data["results"] == []
        assert self.mutate("configurer/", titre="Refus").status_code == 400
        assert self.mutate("configurer/", cours=None).status_code == 200

    def test_version_conflict_rolls_back_owner_course_and_audit_and_rejects_arbitrary_identifiers(self):
        assert self.create_bound().status_code == 201
        stale = self.project["version"]
        assert self.mutate("configurer/", titre="Version suivante").status_code == 200
        before = list(self.events().values())
        project_before = PedagogicalProject.objects.values().get(pk=self.project["id"])
        response = self.mutate(
            "configurer/", version=stale, responsable=self.staff.pk, cours=self.alternative.pk, titre="Perdu"
        )
        assert response.status_code == 409, response.data
        for value in (0, "course-v1:SIS+PROJECT-A+sis", {"id": self.alternative.pk}):
            assert self.mutate("configurer/", cours=value).status_code == 400
        assert list(self.events().values()) == before
        assert PedagogicalProject.objects.values().get(pk=self.project["id"]) == project_before

    def test_course_access_never_grants_project_or_team_access_and_module_switch_closes_selector(self):
        assert self.create_bound().status_code == 201
        reader = self.user("course-only-reader", "enseignant")
        self.course_access(reader)
        assert self.search(user=reader).status_code == 403
        assert self.search(user=reader, projet=self.project["id"]).status_code == 404
        self.login(reader)
        assert self.client.get(self.url()).status_code == 404
        assert self.client.get(self.url("equipes/")).status_code == 404
        assert (
            self.client.post(
                self.url("configurer/"), {"version": 1, "cours": self.course.pk}, format="json"
            ).status_code
            == 404
        )
        self.toggle(False)
        assert self.search().status_code == 403
