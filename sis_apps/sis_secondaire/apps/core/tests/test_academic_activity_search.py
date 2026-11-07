"""Mounted search of mapped secondary evaluations, never a native LMS catalogue."""

import uuid
from types import SimpleNamespace
from unittest.mock import patch

from apps.classes.models import Classe, Matiere
from apps.core.api import AcademicSearchView
from apps.eleves.models import Eleve, EleveTuteur, Tuteur
from apps.enseignants.models import AffectationEnseignant, Personnel
from apps.etablissement.models import AnneeScolaire, Etablissement, Niveau, Periode
from apps.integration.models import EdxAssessmentMapping, EdxCourseMapping, EdxEnrollment, OutboxEvent
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.notes.api import EvaluationsViewSet
from apps.notes.models import Evaluation, Note
from apps.utilisateurs.models import Utilisateur
from django.contrib.auth.models import Permission
from django.test import override_settings
from django.urls import resolve
from django_tenants.utils import schema_context
from rest_framework.exceptions import PermissionDenied
from rest_framework.test import APIRequestFactory, force_authenticate


@override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
class AcademicActivitySearchAPITests(TenantAPITestCase):
    url = "/api/v1/core/recherche-academique/"
    source_url = "/api/v1/notes/evaluations/"
    params = {"ressource": "evaluations_lms", "q": "quantum"}

    def setUp(self):
        self.permission = Permission.objects.get(content_type__app_label="notes", codename="view_evaluation")
        self.manager = self._user("manager", "personnel_administratif")
        self.manager.is_staff = True
        self.manager.save(update_fields=["is_staff"])
        self.teacher = self._teacher("teacher")
        self.peer_teacher = self._teacher("peer")
        self.other = Etablissement(schema_name=f"activity_search_{uuid.uuid4().hex[:12]}")
        self.setup_tenant(self.other)
        self.other.auto_create_schema = False
        with schema_context("public"):
            self.other.save()
        self.course = self._course(self.tenant, "LOCAL")
        self.other_course = self._course(self.tenant, "OTHER")
        self.foreign_course = self._course(self.other, "FOREIGN")
        self.period = self._period(self.course.classe.annee_scolaire)
        self.other_period = self._period(self.course.classe.annee_scolaire, number=2)
        self.foreign_period = self._period(self.foreign_course.classe.annee_scolaire)
        self.own = self._evaluation("OWN", self.course, self.teacher)
        self.peer = self._evaluation("PEER", self.course, self.peer_teacher)
        self.other_scope = self._evaluation("OTHER", self.other_course, self.teacher, periode=self.other_period)
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

    def _teacher(self, name, tenant=None):
        return Personnel.objects.create(
            user=self._user(name, "enseignant", tenant),
            matricule=f"ACTIVITY-{name}",
            date_embauche="2025-09-01",
        )

    def _authenticate(self, user):
        self.client.force_authenticate(Utilisateur.objects.get(pk=user.pk) if user else None)

    def _course(self, tenant, code):
        year, _ = AnneeScolaire.objects.get_or_create(
            etablissement=tenant,
            libelle="2026-2027",
            defaults={"date_debut": "2026-09-01", "date_fin": "2027-08-31"},
        )
        level, _ = Niveau.objects.get_or_create(etablissement=tenant, code="6e", defaults={"libelle": "Private level"})
        classroom = Classe.objects.create(
            etablissement=tenant,
            annee_scolaire=year,
            niveau=level,
            nom=f"Private class {code}",
        )
        subject = Matiere.objects.create(etablissement=tenant, code=code, nom=f"Private subject {code}")
        return EdxCourseMapping.objects.create(
            classe=classroom,
            matiere=subject,
            course_id=f"course-v1:SIS-S+{code}+sis",
            course_name=f"Private course {code}",
        )

    def _period(self, year, number=1):
        return Periode.objects.create(
            annee_scolaire=year,
            type="trimestre",
            numero=number,
            date_debut="2026-09-01",
            date_fin="2027-08-31",
        )

    def _evaluation(self, code, course, teacher, mapped=True, **kwargs):
        evaluation = Evaluation.objects.create(
            titre=f"Quantum {code}",
            description="Private assessment description",
            matiere=course.matiere,
            classe=course.classe,
            periode=kwargs.pop("periode", self.period),
            enseignant=teacher,
            date="2026-11-15",
            **kwargs,
        )
        if mapped:
            EdxAssessmentMapping.objects.create(
                course=course,
                evaluation=evaluation,
                subsection_id=f"block-v1:SIS-S+{course.matiere.code}+sis+type@sequential+block@{code}",
            )
        return evaluation

    def _search(self, **params):
        return self.client.get(self.url, {**self.params, **params}, secure=True)

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
            "Private subject",
            "Private course",
            "Private class",
            "Private level",
        ):
            assert private_value not in str(result.data)
        return result

    def _assert_denied(self):
        result = self._search()
        assert result.status_code in (401, 403), result.data
        assert "results" not in result.data
        assert "Quantum" not in str(result.data)
        assert "block-v1:" not in str(result.data)

    def _scope(self, user, constraints):
        user.attributs_acces = {"permission_scopes": {"notes.view_evaluation": constraints}}
        user.save(update_fields=["attributs_acces"])
        self._authenticate(user)

    def test_only_real_mapped_evaluations_have_native_detail_targets_without_lms_io(self):
        before = list(EdxAssessmentMapping.objects.order_by("pk").values())
        counts = (OutboxEvent.objects.count(), Note.objects.count(), Evaluation.objects.count())
        with (
            patch("apps.integration.api.SyncService") as service,
            patch("apps.integration.api.get_edx_client") as remote,
        ):
            result = self._assert_results([self.own, self.peer, self.other_scope])
            assert self.client.post(self.url, self.params, format="json", secure=True).status_code == 405
            service.assert_not_called()
            remote.assert_not_called()
        source = self.client.get(self.source_url, {"search": "quantum", "page_size": 50}, secure=True)
        assert source.status_code == 200, source.data
        assert {row["id"] for row in source.data["results"]} == {item.pk for item in self.evaluations}
        for row in result.data["results"]:
            target = f"{self.source_url}{row['id']}/"
            assert resolve(target).url_name == "evaluation-detail"
            detail = self.client.get(target, secure=True)
            assert detail.status_code == 200, detail.data
            assert detail.data["id"] == row["id"]
            assert detail.data["titre"] == row["nom"]
        assert list(EdxAssessmentMapping.objects.order_by("pk").values()) == before
        assert (OutboxEvent.objects.count(), Note.objects.count(), Evaluation.objects.count()) == counts

    def test_title_and_subsection_search_does_not_match_private_metadata_or_sql_wildcards(self):
        for term in ("  qUaNtUm OwN  ", self.own.edx_assessment.subsection_id.lower()):
            result = self._search(q=term)
            assert result.status_code == 200, result.data
            assert [row["id"] for row in result.data["results"]] == [self.own.pk]
        for term in (
            "Private assessment",
            "PrivateSurname",
            "Private course",
            "Private subject",
            "Private class",
            self.course.course_id,
            "UNMAPPED",
            "not-matched",
            "%%",
            "__",
            "' OR 1=1 --",
            "<script>",
        ):
            result = self._search(q=term)
            assert result.status_code == 200, result.data
            assert result.data["count"] == 0
        literal = self._evaluation("100%_EXACT", self.course, self.teacher)
        result = self._search(q="%_")
        assert result.status_code == 200, result.data
        assert [row["id"] for row in result.data["results"]] == [literal.pk]

    def test_personnel_ownership_is_not_expanded_by_assignment_or_principal_user(self):
        self.course.classe.prof_principal = self.teacher.user
        self.course.classe.save(update_fields=["prof_principal"])
        assignment = AffectationEnseignant.objects.create(
            enseignant=self.teacher,
            matiere=self.course.matiere,
            annee_scolaire=self.course.classe.annee_scolaire,
        )
        assignment.classes.add(self.course.classe)
        self._authenticate(self.teacher.user)
        self._assert_results([self.own, self.other_scope])
        assert self.client.get(f"{self.source_url}{self.peer.pk}/", secure=True).status_code == 404
        self.own.enseignant = self.peer_teacher
        self.own.save(update_fields=["enseignant"])
        self._assert_results([self.other_scope])
        assert self.client.get(f"{self.source_url}{self.own.pk}/", secure=True).status_code == 404
        self._authenticate(self._user("no-personnel", "enseignant"))
        self._assert_denied()

    def test_authoritative_source_permissions_and_queryset_are_used(self):
        with patch.object(EvaluationsViewSet, "check_permissions", side_effect=PermissionDenied()):
            self._assert_denied()
        with patch.object(EvaluationsViewSet, "get_queryset", return_value=Evaluation.objects.filter(pk=self.peer.pk)):
            self._assert_results([self.peer])
        with patch.object(EvaluationsViewSet, "get_queryset", return_value=Evaluation.objects.none()):
            self._assert_denied()

    def test_staff_and_legacy_roles_do_not_bypass_revoked_model_permission(self):
        self._assert_results([self.own, self.peer, self.other_scope])
        self.manager.user_permissions.remove(self.permission)
        self._authenticate(self.manager)
        self._assert_denied()
        assert self.client.get(f"{self.source_url}{self.own.pk}/", secure=True).status_code == 404
        for user in (self.teacher.user, self._user("direction", "direction", grant=False)):
            user.user_permissions.clear()
            self._authenticate(user)
            self._assert_denied()

    def test_scopes_intersect_teacher_ownership_and_restrict_source_access(self):
        for key, value in {
            "classes": self.own.classe_id,
            "matieres": self.own.matiere_id,
            "periodes": self.own.periode_id,
        }.items():
            with self.subTest(scope=key):
                self._scope(self.teacher.user, {key: [value]})
                self._assert_results([self.own])
                assert self.client.get(f"{self.source_url}{self.other_scope.pk}/", secure=True).status_code == 404
        self._scope(self.teacher.user, {"annees": [self.own.classe.annee_scolaire_id]})
        self._assert_results([self.own, self.other_scope])
        self._scope(self.teacher.user, {"annees": [self.foreign_course.classe.annee_scolaire_id]})
        self._assert_results([])
        self._scope(self.teacher.user, {"classes": []})
        self._assert_results([])
        self._scope(self.teacher.user, {"classes": [self.own.classe_id], "matieres": [self.other_scope.matiere_id]})
        self._assert_results([])
        for scope in ({"classes": "*"}, {"classes": "all"}, {"unknown": [self.own.classe_id]}):
            self._scope(self.teacher.user, scope)
            self._assert_denied()
        self._scope(self.manager, {"classes": [self.own.classe_id]})
        self._assert_denied()
        assert self.client.get(f"{self.source_url}{self.own.pk}/", secure=True).status_code == 404

    def test_lms_enrollment_and_parent_portal_do_not_grant_evaluation_search(self):
        pupil_user = self._user("pupil", "eleve", grant=False)
        pupil = Eleve.objects.create(
            etablissement=self.tenant,
            user=pupil_user,
            classe_actuelle=self.course.classe,
            matricule="ACTIVITY-PUPIL",
            date_naissance="2014-01-01",
            lieu_naissance="Paris",
            sexe="F",
            date_inscription="2026-09-01",
        )
        EdxEnrollment.objects.create(eleve=pupil, course=self.course)
        parent = self._user("parent", "parent", grant=False)
        guardian = Tuteur.objects.create(
            etablissement=self.tenant,
            user=parent,
            nom="PrivateSurname",
            prenom="Parent",
            lien_parente="mere",
            telephone="0100000000",
            email="private@example.test",
        )
        EleveTuteur.objects.create(eleve=pupil, tuteur=guardian, autorise_acces_portail=True)
        for user in (pupil_user, parent):
            self._authenticate(user)
            self._assert_denied()
            user.user_permissions.add(self.permission)
            user.is_staff = True
            user.save(update_fields=["is_staff"])
            self._authenticate(user)
            self._assert_denied()
            user.is_superuser = True
            user.save(update_fields=["is_superuser"])
            self._authenticate(user)
            self._assert_denied()

    def test_removed_inactive_blank_and_inconsistent_mappings_disappear(self):
        mapping = self.own.edx_assessment
        original_subsection = mapping.subsection_id
        for changes in ({"actif": False}, {"subsection_id": ""}, {"course": self.foreign_course}):
            with self.subTest(changes=changes):
                for field, value in changes.items():
                    setattr(mapping, field, value)
                mapping.save(update_fields=list(changes))
                self._assert_results([self.peer, self.other_scope])
                mapping.actif = True
                mapping.subsection_id = original_subsection
                mapping.course = self.course
                mapping.save(update_fields=["actif", "subsection_id", "course"])
        for field in ("matiere", "classe"):
            with self.subTest(mismatch=field):
                original = getattr(self.course, field)
                setattr(self.course, field, getattr(self.other_course, field))
                self.course.save(update_fields=[field])
                self._assert_results([self.other_scope])
                setattr(self.course, field, original)
                self.course.save(update_fields=[field])
        for field, value in (("actif", False), ("course_id", "")):
            original = getattr(self.course, field)
            setattr(self.course, field, value)
            self.course.save(update_fields=[field])
            self._assert_results([self.other_scope])
            setattr(self.course, field, original)
            self.course.save(update_fields=[field])
        EdxAssessmentMapping.objects.filter(pk=mapping.pk).delete()
        self._assert_results([self.peer, self.other_scope])
        EdxCourseMapping.objects.filter(pk=self.other_course.pk).delete()
        self._assert_results([self.peer])

    def test_foreign_source_anchors_and_inconsistent_years_are_excluded_even_for_superusers(self):
        foreign_teacher = self._teacher("foreign-teacher", self.other)
        other_year = AnneeScolaire.objects.create(
            etablissement=self.tenant, libelle="2027-2028", date_debut="2027-09-01", date_fin="2028-08-31"
        )
        other_year_period = self._period(other_year)
        self.evaluations.extend(
            [
                self._evaluation("FOREIGN-TEACHER", self.course, foreign_teacher),
                self._evaluation("FOREIGN-PERIOD", self.course, self.teacher, periode=self.foreign_period),
                self._evaluation("WRONG-YEAR", self.other_course, self.teacher, periode=other_year_period),
                self._evaluation("FOREIGN-COURSE", self.foreign_course, foreign_teacher, periode=self.foreign_period),
            ]
        )
        for superuser in (False, True):
            self.manager.is_superuser = superuser
            self.manager.save(update_fields=["is_superuser"])
            self._authenticate(self.manager)
            self._assert_results([self.own, self.peer, self.other_scope])
            for obj, field, value in (
                (self.course.classe, "etablissement", self.other),
                (self.course.classe, "etablissement", None),
                (self.course.matiere, "etablissement", self.other),
                (self.course.matiere, "etablissement", None),
                (self.course.classe, "annee_scolaire", self.foreign_course.classe.annee_scolaire),
                (self.course.classe, "annee_scolaire", other_year),
                (self.course.classe, "niveau", self.foreign_course.classe.niveau),
            ):
                with self.subTest(superuser=superuser, model=obj._meta.label, field=field):
                    original = getattr(obj, field)
                    setattr(obj, field, value)
                    obj.save(update_fields=[field])
                    self._assert_results([self.other_scope])
                    setattr(obj, field, original)
                    obj.save(update_fields=[field])

    def test_foreign_inactive_unbound_and_anonymous_actors_cannot_search(self):
        foreign = self._user("foreign-admin", "personnel_administratif", self.other)
        foreign.is_superuser = True
        foreign.save(update_fields=["is_superuser"])
        self.manager.is_active = False
        self.manager.save(update_fields=["is_active"])
        unbound = self._user("unbound", "personnel_administratif")
        unbound.etablissement = None
        unbound.is_superuser = True
        unbound.save(update_fields=["etablissement", "is_superuser"])
        for user in (foreign, self.manager, unbound, None):
            self._authenticate(user)
            self._assert_denied()

    def test_inactive_missing_public_and_inconsistent_tenants_cannot_search(self):
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
        original = self.tenant.actif
        try:
            self.tenant.actif = False
            self.tenant.save(update_fields=["actif"])
            self._assert_denied()
        finally:
            self.tenant.actif = original
            self.tenant.save(update_fields=["actif"])

    def test_invalid_queries_and_stable_bounded_pagination(self):
        for term in (
            "",
            " ",
            "a",
            "x" * 101,
            " " * 99 + "ab",
            "quantum\n",
            "a\tb",
            "ab\x00",
            "ab\x7f",
            "ab\x85",
        ):
            with self.subTest(term=term):
                result = self._search(q=term)
                assert result.status_code == 400
                assert "q" in result.data
        for term in ("ab", "x" * 100):
            assert self._search(q=term).status_code == 200
        assert self.client.get(self.url, {"ressource": "evaluations_lms"}, secure=True).status_code == 400
        assert self._search(ressource="evaluations_lms,cours").status_code == 400
        for index in range(50):
            self._evaluation(f"PAGE-{index:02}", self.course, self.teacher)
        default = self._search()
        first = self._search(page_size=999)
        second = self.client.get(first.data["next"], secure=True)
        assert default.status_code == first.status_code == second.status_code == 200
        assert default.data["count"] == first.data["count"] == second.data["count"] == 53
        assert len(default.data["results"]) == 20
        assert len(first.data["results"]) == 50
        assert len(second.data["results"]) == 3
        ids = [row["id"] for row in first.data["results"] + second.data["results"]]
        assert ids == sorted(set(ids))
        assert default.data["results"] == first.data["results"][:20]
        assert self._search(page_size=999).data == first.data
        assert first.data["previous"] is None
        assert second.data["previous"]
        assert second.data["next"] is None
