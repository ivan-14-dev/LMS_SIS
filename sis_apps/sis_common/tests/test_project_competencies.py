"""Mounted SQL contracts, shared by both SIS variants; no mocked course authorization."""

import json
from copy import deepcopy
from unittest.mock import patch
from uuid import uuid4

from apps.core.models import PedagogicalProject, ProjectContribution
from apps.integration.models import EdxAccessIntent, EdxCourseMapping, EdxEnrollment, OutboxEvent
from apps.notes.models import Note
from django.conf import settings

from sis_common.institutional_profiles import PROFILES, validate_learning_offering
from sis_common.tests.test_project_courses import MANAGE, READ, ProjectCourseFixture
from sis_common.tests.test_projects import BASE


class ProjectCompetencyTests(ProjectCourseFixture):
    def setUp(self):
        super().setUp()
        self.offering = {
            **deepcopy(PROFILES["primary"]),
            "code": "project_objectives",
            "profile": "primary",
            "version": 1,
        }
        self.offering["assessment"]["criteria"] = [
            {"code": "analyse", "label": "Analyse source"},
            {"code": "argumentation", "label": "Argumentation source"},
        ]
        validate_learning_offering(self.offering)
        self.bind(self.course, self.offering)
        self.bind(self.alternative, self.offering)

    def source(self, course):
        return course.classe if settings.SIS_VARIANT == "secondaire" else course.ecue.ue.maquette.formation

    def bind(self, course, offering):
        source = self.source(course)
        type(source).objects.filter(pk=source.pk).update(offre_configuration=deepcopy(offering))

    def candidates(self, user=None, owner=None, course=None, **params):
        self.login(user or self.manager)
        return self.client.get(
            f"{BASE}competences-candidates/",
            {"responsable": (owner or self.manager).pk, "cours": (course or self.course).pk, **params},
        )

    def create_selected(self, **overrides):
        self.login(self.manager)
        response = self.client.post(
            BASE,
            {
                "titre": "Compétences visées",
                "mode": "collectif",
                "responsable": self.manager.pk,
                "cours": self.course.pk,
                "competences": ["analyse"],
                **overrides,
            },
            format="json",
        )
        if response.status_code == 201:
            self.project = response.data
        return response

    def saved(self):
        return PedagogicalProject.objects.get(pk=self.project["id"])

    def test_select_preserve_remove_and_history_without_official_or_lms_writes(self):
        models = [EdxCourseMapping, EdxEnrollment, EdxAccessIntent, OutboxEvent, Note, ProjectContribution]
        before = [list(model.objects.order_by("pk").values()) for model in models]
        with (
            patch("apps.integration.api.get_edx_client") as remote,
            patch("apps.integration.api.SyncService") as service,
        ):
            result = self.create_selected()
            assert result.status_code == 201, result.data
            assert result.data["competences"] == {
                "version": 1,
                "disponible": True,
                "criteria": [self.offering["assessment"]["criteria"][0]],
            }
            original = deepcopy(self.saved().competences_snapshot)
            assert original["_contexte"]["source"]["model"] == (
                "classes.classe" if settings.SIS_VARIANT == "secondaire" else "formations.formation"
            )
            assert original["_offre"]["code"] == self.offering["code"]
            assert self.mutate("configurer/", titre="Conserver").status_code == 200
            assert self.saved().competences_snapshot == original
            assert self.mutate("configurer/", responsable=self.staff.pk).status_code == 200
            assert self.saved().competences_snapshot == original
            assert self.mutate("configurer/", competences=[]).data["competences"] is None
            assert self.saved().competences_snapshot is None
            assert self.events().first().metadata["competences"] == original
            assert list(self.events())[-1].metadata["avant"]["competences"] == original
            remote.assert_not_called()
            service.assert_not_called()
        assert [list(model.objects.order_by("pk").values()) for model in models] == before

    def test_source_is_bound_snapshot_not_live_tenant_catalogue_and_is_paginated(self):
        self.tenant.configuration_academique = {"learning_offerings": []}
        self.tenant.save(update_fields=["configuration_academique"])
        first = self.candidates(page_size=1)
        assert first.status_code == 200, first.data
        assert first.data["etat"] == "competency"
        assert first.data["count"] == 2 and first.data["next"]
        assert first.data["results"] == [self.offering["assessment"]["criteria"][0]]
        assert self.candidates(page_size=1, page=2).data["results"] == [self.offering["assessment"]["criteria"][1]]
        assert self.create_selected().status_code == 201
        assert "_offre" not in json.dumps(self.project)

    def test_empty_offerings_do_not_fall_back_and_corruption_fails_closed(self):
        self.tenant.configuration_academique = {"learning_offerings": [self.offering]}
        self.tenant.save(update_fields=["configuration_academique"])
        for mode, assessment in (
            ("absente", None),
            ("numeric", {"mode": "numeric", "minimum": 0, "maximum": 20, "pass_mark": 10}),
            ("pass_fail", {"mode": "pass_fail"}),
        ):
            offering = {**self.offering, "assessment": assessment} if assessment else {}
            self.bind(self.course, offering)
            response = self.candidates()
            assert response.status_code == 200, response.data
            assert response.data["etat"] == mode and response.data["results"] == []
            assert self.create_selected().status_code == 400
        for invalid in ([], False, 4, "", {"assessment": {"mode": "competency", "criteria": []}}):
            self.bind(self.course, invalid)
            response = self.candidates()
            assert response.status_code == 400, response.data
            assert "corrompue" in str(response.data)
            assert self.create_selected().status_code == 400
        assert PedagogicalProject.objects.count() == 0

    def test_strict_codes_and_unknown_fields_refuse_without_mutation(self):
        assert self.create_selected().status_code == 201
        original, event_count = self.saved().competences_snapshot, self.events().count()
        for codes in (
            "analyse",
            None,
            {},
            [True],
            [12],
            [" analyse"],
            ["a" * 65],
            ["analyse"] * 2,
            ["unknown"],
            [f"c{number}" for number in range(101)],
            [{"code": "analyse", "label": "Client"}],
        ):
            response = self.mutate("configurer/", competences=codes)
            assert response.status_code == 400, response.data
            assert self.saved().version == 1
            assert self.saved().competences_snapshot == original
            assert self.events().count() == event_count
        for extra in ({"competences_snapshot": original}, {"offre": self.offering}, {"label": "Client"}):
            assert self.mutate("configurer/", **extra).status_code == 400
        assert self.mutate("configurer/", version=9, competences=[]).status_code == 409
        assert self.saved().competences_snapshot == original and self.events().count() == event_count

    def test_course_clear_rebind_and_offering_change_require_explicit_reselection(self):
        assert self.create_selected().status_code == 201
        original = deepcopy(self.saved().competences_snapshot)
        for course_id in (None, self.alternative.pk):
            assert self.mutate("configurer/", cours=course_id).status_code == 400
            assert self.saved().competences_snapshot == original
        changed = deepcopy(self.offering)
        changed["assessment"]["criteria"][0]["label"] = "Analyse renommée"
        self.bind(self.course, changed)
        assert self.mutate("configurer/", titre="Conserver périmé").status_code == 400
        assert self.saved().version == 1
        self.login(self.manager)
        assert self.client.get(self.url()).data["competences"]["criteria"][0]["label"] == "Analyse source"
        assert self.mutate("configurer/", competences=["analyse"]).status_code == 200
        assert self.saved().competences_snapshot["criteria"][0]["label"] == "Analyse renommée"
        assert self.events().first().metadata["competences"] == original
        changed["assessment"]["criteria"] = changed["assessment"]["criteria"][1:]
        self.bind(self.course, changed)
        assert self.mutate("configurer/", competences=["analyse"]).status_code == 400
        assert self.mutate("configurer/", titre="Critère retiré").status_code == 400
        assert self.mutate("configurer/", cours=self.alternative.pk, competences=["argumentation"]).status_code == 200
        assert self.mutate("configurer/", cours=None, competences=[]).status_code == 200
        assert self.saved().cours_id is None and self.saved().competences_snapshot is None

    def test_teacher_assignment_and_admin_owner_intersection_are_revalidated(self):
        assignment = self.assign_teacher(self.manager, self.course)
        self.scopes(self.manager, **{READ: {"cours": [self.course.pk]}, MANAGE: {"responsable_id": [self.manager.pk]}})
        assert self.candidates().data["count"] == 2
        assert self.candidates(course=self.alternative).status_code == 400
        assert self.create_selected().status_code == 201
        assert self.mutate("configurer/", titre="Avant révocation").status_code == 200
        assert self.candidates(user=self.staff, owner=self.manager, projet=self.project["id"]).status_code == 200
        self.scopes(self.staff, **{READ: {"cours": []}})
        assert self.candidates(user=self.staff, owner=self.manager, projet=self.project["id"]).status_code == 400
        assert self.mutate("configurer/", user=self.staff, competences=["analyse"]).status_code == 400
        self.scopes(self.manager, **{READ: {"cours": [self.course.pk]}})
        assert self.mutate("configurer/", responsable=self.staff.pk).status_code == 400
        assignment.delete()
        assert self.candidates(projet=self.project["id"]).status_code == 400
        self.login(self.manager)
        assert self.client.get(self.url()).data["competences"] == {"disponible": False}
        history = self.client.get(self.url("historique/"))
        assert history.status_code == 200
        assert "Analyse source" not in json.dumps(history.data, default=str)
        assert "analyse" not in json.dumps(history.data, default=str)
        assert "_sha256" not in json.dumps(history.data, default=str)
        assert self.mutate("equipes/", nom="Toujours disponible", membres=[self.alice.pk]).status_code == 201
        self.login(self.alice)
        assert self.client.get(self.url()).data["competences"] == {"disponible": False}

    def test_academic_move_masks_snapshot_and_history_even_if_course_stays_visible(self):
        assert self.create_selected().status_code == 201
        source = self.source(self.course)
        if settings.SIS_VARIANT == "secondaire":
            source.niveau = self.alternative.classe.niveau
            source.save(update_fields=["niveau"])
        else:
            from apps.structure.models import Departement, Faculte

            faculty = Faculte.objects.create(universite=self.tenant, code="MOVE", nom="Déplacement")
            source.departement = Departement.objects.create(faculte=faculty, code="MOVE", nom="Déplacement")
            source.save(update_fields=["departement"])
        self.login(self.manager)
        result = self.client.get(self.url())
        assert result.data["cours"]["disponible"] is True
        assert result.data["competences"] == {"disponible": False}
        history = self.client.get(self.url("historique/"))
        assert "Analyse source" not in json.dumps(history.data, default=str)
        assert self.mutate("configurer/", titre="Conserver ancien contexte").status_code == 400
        assert self.mutate("configurer/", competences=["analyse"]).status_code == 200

    def test_foreign_academic_ancestry_is_rejected_before_reading_offering(self):
        from django_tenants.utils import schema_context

        foreign = type(self.tenant)(schema_name=f"project_competencies_{uuid4().hex[:12]}")
        self.setup_tenant(foreign)
        foreign.auto_create_schema = False
        with schema_context("public"):
            foreign.save()
        source = self.source(self.course)
        if settings.SIS_VARIANT == "secondaire":
            source.niveau.etablissement = foreign
            source.niveau.save(update_fields=["etablissement"])
        else:
            from apps.structure.models import Departement, EcoleDoctorale, Faculte

            faculty = Faculte.objects.create(universite=foreign, code="FOREIGN", nom="Étranger")
            source.departement = Departement.objects.create(faculte=faculty, code="FOREIGN", nom="Étranger")
            source.save(update_fields=["departement"])
        with patch("sis_common.project_competencies.validate_learning_offering") as validator:
            assert self.candidates().status_code == 400
            assert self.create_selected().status_code == 400
            validator.assert_not_called()
        if settings.SIS_VARIANT == "superieur":
            source.departement = None
            source.ecole_doctorale = EcoleDoctorale.objects.create(universite=foreign, code="FOREIGN", nom="Étranger")
            source.save(update_fields=["departement", "ecole_doctorale"])
            assert self.candidates().status_code == 400

    def test_unbound_and_legacy_rows_have_no_competency_metadata_or_requirement(self):
        self.manager.user_permissions.remove(self.course_permission)
        self.create_project()
        assert self.project["competences"] is None
        assert self.mutate("configurer/", titre="Sans compétences").status_code == 200
        assert self.mutate("configurer/", competences=["analyse"]).status_code == 400
        self.login(self.manager)
        assert self.client.get(self.url("historique/")).status_code == 200

    def test_corrupted_source_cannot_refresh_a_snapshot_but_explicit_removal_recovers(self):
        assert self.create_selected().status_code == 201
        original = deepcopy(self.saved().competences_snapshot)
        self.bind(self.course, {"invalid": "configuration"})
        for values in ({"titre": "Conserver"}, {"competences": ["analyse"]}):
            assert self.mutate("configurer/", **values).status_code == 400
            assert self.saved().competences_snapshot == original
        assert self.mutate("configurer/", competences=[]).status_code == 200
        assert self.saved().competences_snapshot is None
        assert self.events().first().metadata["competences"] == original
