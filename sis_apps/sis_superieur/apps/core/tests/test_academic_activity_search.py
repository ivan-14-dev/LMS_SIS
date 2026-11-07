"""Mounted search of mapped SIS evaluations, not a native LMS activity catalogue."""

import uuid
from types import SimpleNamespace
from unittest.mock import patch

from apps.core.api import AcademicSearchView
from apps.etablissement.models import AnneeUniversitaire, Semestre, Universite
from apps.etudiants.models import Etudiant, InscriptionAdministrative, InscriptionPedagogique
from apps.formations.models import Formation, MaquetteFormation
from apps.integration.models import EdxAssessmentMapping, EdxCourseMapping, OutboxEvent
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.notes.api import EvaluationsViewSet
from apps.notes.models import Evaluation, Note
from apps.structure.models import Departement, EcoleDoctorale, Faculte
from apps.ue_ecue.models import ECUE, UE
from apps.utilisateurs.models import Utilisateur
from django.contrib.auth.models import Permission
from django.urls import resolve
from django_tenants.utils import schema_context
from rest_framework.exceptions import PermissionDenied
from rest_framework.test import APIRequestFactory, force_authenticate


class AcademicActivitySearchAPITests(TenantAPITestCase):
    url = "/api/v1/core/recherche-academique/"
    source_url = "/api/v1/notes/evaluations/"
    params = {"ressource": "evaluations_lms", "q": "quantum"}

    def setUp(self):
        self.permission = Permission.objects.get(content_type__app_label="notes", codename="view_evaluation")
        self.teacher = self._user("teacher", "enseignant")
        self.peer_teacher = self._user("peer", "enseignant")
        self.manager = self._user("manager", "autre")
        self.manager.is_staff = True
        self.manager.save(update_fields=["is_staff"])
        self.other = Universite(schema_name=f"activity_search_{uuid.uuid4().hex[:12]}")
        self.setup_tenant(self.other)
        self.other.auto_create_schema = False
        with schema_context("public"):
            self.other.save()
        self.course = self._course(self.tenant, "LOCAL")
        self.other_course = self._course(self.tenant, "OTHER", semester_number=2)
        self.foreign_course = self._course(self.other, "FOREIGN")
        self.own = self._evaluation("OWN", self.course, self.teacher)
        self.peer = self._evaluation("PEER", self.course, self.peer_teacher)
        self.other_scope = self._evaluation("OTHER", self.other_course, self.teacher)
        self.unmapped = self._evaluation("UNMAPPED", self.course, self.teacher, mapped=False)
        self.evaluations = [self.own, self.peer, self.other_scope, self.unmapped]
        self._authenticate(self.manager)

    def _user(self, name, role, tenant=None, grant=True):
        user = Utilisateur.objects.create_user(
            f"activity-search-{name}",
            role=role,
            etablissement=tenant or self.tenant,
            first_name="PrivateTeacherName",
            last_name="PrivateSurname",
        )
        if grant:
            user.user_permissions.add(self.permission)
        return user

    def _authenticate(self, user):
        self.client.force_authenticate(Utilisateur.objects.get(pk=user.pk) if user else None)

    def _course(self, tenant, code, semester_number=1):
        year, _ = AnneeUniversitaire.objects.get_or_create(
            universite=tenant,
            libelle="2025-2026",
            defaults={"date_debut": "2025-09-01", "date_fin": "2026-06-30"},
        )
        semester, _ = Semestre.objects.get_or_create(
            annee_universitaire=year,
            numero=semester_number,
            defaults={"type": "unique", "date_debut": "2025-09-01", "date_fin": "2026-06-30"},
        )
        faculty = Faculte.objects.create(universite=tenant, code=code, nom=f"Private faculty {code}")
        department = Departement.objects.create(faculte=faculty, code=code, nom=f"Private department {code}")
        formation = Formation.objects.create(departement=department, code=code, nom="Private formation", type="licence")
        maquette = MaquetteFormation.objects.create(formation=formation, annee_universitaire=year)
        unit = UE.objects.create(
            code=code, nom="Private teaching unit", maquette=maquette, semestre=semester, credits_ects=6
        )
        ecue = ECUE.objects.create(ue=unit, code=code, nom="Private ECUE", credits_ects=3)
        return EdxCourseMapping.objects.create(
            ecue=ecue, course_id=f"course-v1:SIS-U+{code}+sis", course_name=f"Private course {code}"
        )

    def _evaluation(self, code, course, teacher, mapped=True, **kwargs):
        evaluation = Evaluation.objects.create(
            titre=f"Quantum {code}",
            description="Private assessment description",
            ecue=course.ecue,
            semestre=kwargs.pop("semestre", course.ecue.ue.semestre),
            enseignant=teacher,
            modalite="cc",
            date="2026-01-15",
            **kwargs,
        )
        if mapped:
            EdxAssessmentMapping.objects.create(
                course=course,
                evaluation=evaluation,
                subsection_id=f"block-v1:SIS-U+{course.ecue.code}+sis+type@sequential+block@{code}",
            )
        return evaluation

    def _search(self, **params):
        return self.client.get(self.url, {**self.params, **params})

    def _assert_results(self, expected):
        result = self._search(page_size=50)
        assert result.status_code == 200, result.data
        assert result.data["count"] == len(expected)
        assert result.data["results"] == [
            {"id": item.pk, "code": item.edx_assessment.subsection_id, "nom": item.titre}
            for item in sorted(expected, key=lambda item: item.pk)
        ]
        for item in self.evaluations:
            if item not in expected:
                assert item.titre not in str(result.data)
        for private_value in (
            "PrivateTeacherName",
            "PrivateSurname",
            "Private assessment",
            "Private ECUE",
            "Private course",
            "Private formation",
            "Private faculty",
            "Private department",
        ):
            assert private_value not in str(result.data)
        return result

    def _assert_denied(self):
        result = self._search()
        assert result.status_code in (401, 403), result.data
        assert "results" not in result.data
        assert "Quantum" not in str(result.data)
        assert "block-v1:" not in str(result.data)

    def test_real_mapped_evaluations_have_existing_detail_targets_without_lms_io(self):
        before = list(EdxAssessmentMapping.objects.order_by("pk").values())
        outbox_count = OutboxEvent.objects.count()
        note_count = Note.objects.count()
        with (
            patch("apps.integration.api.SyncService") as service,
            patch("apps.integration.api.get_edx_client") as remote,
        ):
            result = self._assert_results([self.own, self.peer, self.other_scope])
            assert self.client.post(self.url, self.params, format="json").status_code == 405
            service.assert_not_called()
            remote.assert_not_called()
        source = self.client.get(self.source_url, {"search": "quantum", "page_size": "50"})
        assert source.status_code == 200
        assert {row["id"] for row in source.data["results"]} == {item.pk for item in self.evaluations}
        for row in result.data["results"]:
            target = f"{self.source_url}{row['id']}/"
            assert resolve(target).url_name == "evaluation-detail"
            detail = self.client.get(target)
            assert detail.status_code == 200, detail.data
            assert detail.data["id"] == row["id"]
            assert detail.data["titre"] == row["nom"]
        assert list(EdxAssessmentMapping.objects.order_by("pk").values()) == before
        assert OutboxEvent.objects.count() == outbox_count
        assert Note.objects.count() == note_count

    def test_search_uses_title_or_subsection_not_private_metadata(self):
        for term in ("  qUaNtUm OwN  ", self.own.edx_assessment.subsection_id.lower()):
            result = self._search(q=term)
            assert result.status_code == 200
            assert [row["id"] for row in result.data["results"]] == [self.own.pk]
        for term in ("Private assessment", "PrivateSurname", "Private course", "Private ECUE", "not-matched"):
            result = self._search(q=term)
            assert result.status_code == 200
            assert result.data["count"] == 0

    def test_teacher_and_researcher_keep_source_ownership_and_reassignment(self):
        for role in ("enseignant", "chercheur"):
            self.teacher.role = role
            self.teacher.save(update_fields=["role"])
            self._authenticate(self.teacher)
            self._assert_results([self.own, self.other_scope])
            assert self.client.get(f"{self.source_url}{self.peer.pk}/").status_code == 404
        self.own.enseignant = self.peer_teacher
        self.own.save(update_fields=["enseignant"])
        self._assert_results([self.other_scope])
        assert self.client.get(f"{self.source_url}{self.own.pk}/").status_code == 404

    def test_authoritative_source_permissions_and_queryset_are_used(self):
        with patch.object(EvaluationsViewSet, "check_permissions", side_effect=PermissionDenied()):
            self._assert_denied()
        with patch.object(EvaluationsViewSet, "get_queryset", return_value=Evaluation.objects.filter(pk=self.peer.pk)):
            self._assert_results([self.peer])
        with patch.object(EvaluationsViewSet, "get_queryset", return_value=Evaluation.objects.none()):
            self._assert_denied()

    def test_model_grants_staff_and_legacy_roles_do_not_bypass_revocation(self):
        self._assert_results([self.own, self.peer, self.other_scope])
        self.manager.user_permissions.remove(self.permission)
        self._authenticate(self.manager)
        self._assert_denied()
        assert self.client.get(f"{self.source_url}{self.own.pk}/").status_code == 404
        for user in (self.teacher, self._user("registry", "scolarite", grant=False)):
            user.user_permissions.clear()
            self._authenticate(user)
            self._assert_denied()
        self.manager.user_permissions.add(self.permission)
        self.manager.role = "parent"
        self.manager.save(update_fields=["role"])
        self._authenticate(self.manager)
        self._assert_denied()

    def test_contextual_scopes_intersect_teacher_ownership_and_revoke_immediately(self):
        ecue = self.course.ecue
        contexts = {
            "formations": ecue.ue.maquette.formation_id,
            "facultes": ecue.ue.maquette.formation.departement.faculte_id,
            "departements": ecue.ue.maquette.formation.departement_id,
            "semestres": self.own.semestre_id,
            "ues": ecue.ue_id,
            "ecues": ecue.pk,
        }
        for key, value in contexts.items():
            self.teacher.attributs_acces = {"permission_scopes": {"notes.view_evaluation": {key: [value]}}}
            self.teacher.save(update_fields=["attributs_acces"])
            self._authenticate(self.teacher)
            self._assert_results([self.own])
            assert self.client.get(f"{self.source_url}{self.other_scope.pk}/").status_code == 404
        self.teacher.attributs_acces = {
            "permission_scopes": {"notes.view_evaluation": {"annees": [self.own.semestre.annee_universitaire_id]}}
        }
        self.teacher.save(update_fields=["attributs_acces"])
        self._authenticate(self.teacher)
        self._assert_results([self.own, self.other_scope])
        self.teacher.attributs_acces = {"permission_scopes": {"notes.view_evaluation": {"ecues": []}}}
        self.teacher.save(update_fields=["attributs_acces"])
        self._authenticate(self.teacher)
        self._assert_results([])
        for scope in ({"ecues": "all"}, {"unknown": [ecue.pk]}):
            self.teacher.attributs_acces = {"permission_scopes": {"notes.view_evaluation": scope}}
            self.teacher.save(update_fields=["attributs_acces"])
            self._authenticate(self.teacher)
            self._assert_denied()
        self.manager.attributs_acces = {"permission_scopes": {"notes.view_evaluation": {"ecues": [ecue.pk]}}}
        self.manager.save(update_fields=["attributs_acces"])
        self._authenticate(self.manager)
        self._assert_denied()
        assert self.client.get(f"{self.source_url}{self.own.pk}/").status_code == 404

    def test_enrollment_does_not_invent_learner_or_parent_evaluation_visibility(self):
        learner_user = self._user("learner", "etudiant", grant=False)
        learner = Etudiant.objects.create(
            universite=self.tenant,
            user=learner_user,
            matricule="ACTIVITY-LEARNER",
            date_naissance="2003-01-01",
            lieu_naissance="Paris",
            sexe="F",
        )
        enrollment = InscriptionAdministrative.objects.create(
            etudiant=learner,
            annee_universitaire=self.own.semestre.annee_universitaire,
            formation=self.course.ecue.ue.maquette.formation,
            statut="validee",
            date_inscription="2025-09-01",
        )
        pedagogic = InscriptionPedagogique.objects.create(
            inscription_admin=enrollment, semestre=self.own.semestre, statut="validee"
        )
        pedagogic.ecues.add(self.course.ecue)
        self._authenticate(learner_user)
        assert self.client.get(f"{self.source_url}{self.own.pk}/").status_code == 404
        self._assert_denied()
        learner_user.user_permissions.add(self.permission)
        for role in ("etudiant", "doctorant", "parent"):
            learner_user.role = role
            learner_user.is_staff = True
            learner_user.save(update_fields=["role", "is_staff"])
            self._authenticate(learner_user)
            self._assert_denied()

    def test_removed_inactive_blank_and_inconsistent_mappings_disappear(self):
        mapping = self.own.edx_assessment
        original_subsection = mapping.subsection_id
        for changes in (
            {"actif": False},
            {"subsection_id": ""},
            {"course": self.other_course},
            {"course": self.foreign_course},
        ):
            for field, value in changes.items():
                setattr(mapping, field, value)
            mapping.save(update_fields=list(changes))
            self._assert_results([self.peer, self.other_scope])
            mapping.actif = True
            mapping.subsection_id = original_subsection
            mapping.course = self.course
            mapping.save(update_fields=["actif", "subsection_id", "course"])
        self.course.actif = False
        self.course.save(update_fields=["actif"])
        self._assert_results([self.other_scope])
        self.course.actif = True
        self.course.save(update_fields=["actif"])
        course_id = self.course.course_id
        self.course.course_id = ""
        self.course.save(update_fields=["course_id"])
        self._assert_results([self.other_scope])
        self.course.course_id = course_id
        self.course.save(update_fields=["course_id"])
        EdxAssessmentMapping.objects.filter(pk=mapping.pk).delete()
        self._assert_results([self.peer, self.other_scope])
        EdxCourseMapping.objects.filter(pk=self.other_course.pk).delete()
        self._assert_results([self.peer])

    def test_every_evaluation_and_curriculum_tenant_anchor_is_checked(self):
        foreign_teacher = self._user("foreign-teacher", "enseignant", self.other)
        foreign_period = self.foreign_course.ecue.ue.semestre
        extras = [
            self._evaluation("FOREIGN-TEACHER", self.course, foreign_teacher),
            self._evaluation("FOREIGN-PERIOD", self.course, self.teacher, semestre=foreign_period),
            self._evaluation("FOREIGN-ECUE", self.foreign_course, self.teacher, semestre=self.own.semestre),
        ]
        self.evaluations.extend(extras)
        self._assert_results([self.own, self.peer, self.other_scope])
        local_unit = self.course.ecue.ue
        original_period = local_unit.semestre
        local_unit.semestre = foreign_period
        local_unit.save(update_fields=["semestre"])
        self._assert_results([self.other_scope])
        local_unit.semestre = original_period
        local_unit.save(update_fields=["semestre"])
        maquette = local_unit.maquette
        maquette.annee_universitaire = foreign_period.annee_universitaire
        maquette.save(update_fields=["annee_universitaire"])
        self._assert_results([self.other_scope])
        maquette.annee_universitaire = original_period.annee_universitaire
        maquette.save(update_fields=["annee_universitaire"])
        formation = maquette.formation
        formation.departement = self.foreign_course.ecue.ue.maquette.formation.departement
        formation.save(update_fields=["departement"])
        self._assert_results([self.other_scope])
        formation.departement = None
        formation.ecole_doctorale = EcoleDoctorale.objects.create(
            universite=self.other, nom="Private school", code="ED"
        )
        formation.save(update_fields=["departement", "ecole_doctorale"])
        self._assert_results([self.other_scope])

    def test_foreign_inactive_unbound_and_anonymous_actors_are_denied(self):
        foreign = self._user("foreign-admin", "autre", self.other)
        foreign.is_superuser = True
        foreign.save(update_fields=["is_superuser"])
        self.manager.is_active = False
        self.manager.save(update_fields=["is_active"])
        unbound = self._user("unbound", "autre")
        unbound.etablissement = None
        unbound.is_superuser = True
        unbound.save(update_fields=["etablissement", "is_superuser"])
        for user in (foreign, self.manager, unbound, None):
            self._authenticate(user)
            self._assert_denied()

    def test_missing_public_and_inconsistent_database_tenants_are_denied(self):
        factory = APIRequestFactory()
        view = AcademicSearchView.as_view(throttle_classes=[])
        for tenant in (
            None,
            SimpleNamespace(pk=self.tenant.pk, schema_name="public"),
            SimpleNamespace(pk=self.tenant.pk, schema_name="different_schema"),
            SimpleNamespace(pk=self.tenant.pk + 100, schema_name=self.tenant.schema_name),
        ):
            request = factory.get(self.url, self.params)
            request.tenant = tenant
            force_authenticate(request, self.manager)
            result = view(request)
            assert result.status_code == 403
            assert "Quantum" not in str(result.data)
        with schema_context("public"):
            request = factory.get(self.url, self.params)
            request.tenant = self.tenant
            force_authenticate(request, self.manager)
            assert view(request).status_code == 403

    def test_query_validation_and_stable_bounded_pagination(self):
        for term in ("", " ", "a", "x" * 101, "quantum\n", "quantum\x7f", " " * 99 + "ab"):
            assert self._search(q=term).status_code == 400
        for index in range(50):
            self._evaluation(f"PAGE-{index:02}", self.course, self.teacher)
        default = self._search()
        first = self._search(page_size=999)
        second = self._search(page_size=999, page=2)
        assert default.status_code == first.status_code == second.status_code == 200
        assert default.data["count"] == first.data["count"] == second.data["count"] == 53
        assert len(default.data["results"]) == 20
        assert len(first.data["results"]) == 50
        assert len(second.data["results"]) == 3
        ids = [row["id"] for row in first.data["results"] + second.data["results"]]
        assert ids == sorted(set(ids))
        assert first.data["next"] and second.data["previous"]
        assert second.data["next"] is None
