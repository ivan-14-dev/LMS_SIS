"""The native LMS mapping list, detail and typed course search share visibility."""

import uuid
from types import SimpleNamespace
from unittest.mock import patch

from apps.core.api import AcademicSearchView
from apps.etablissement.models import AnneeUniversitaire, Semestre, Universite
from apps.formations.models import Formation, MaquetteFormation
from apps.integration.api import course_mapping_detail, course_mappings
from apps.integration.models import EdxCourseMapping, OutboxEvent
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.ue_ecue.models import ECUE, UE
from apps.utilisateurs.models import Utilisateur
from django.contrib.auth.models import Permission
from django.urls import resolve
from django_tenants.utils import schema_context
from rest_framework.pagination import PageNumberPagination
from rest_framework.test import APIRequestFactory, force_authenticate


class CourseSearchAPITests(TenantAPITestCase):
    search_url = "/api/v1/core/recherche-academique/"
    mappings_url = "/api/v1/integration/mappings/courses/"

    def setUp(self):
        self.admin = Utilisateur.objects.create_user(
            "course-search-admin", role="autre", is_staff=True, etablissement=self.tenant
        )
        self.client.force_authenticate(self.admin)
        self.other = Universite(schema_name=f"course_search_{uuid.uuid4().hex[:12]}")
        self.setup_tenant(self.other)
        self.other.auto_create_schema = False
        with schema_context("public"):
            self.other.save()
        local_maquette, local_semester = self._curriculum(self.tenant, "LOCAL")
        foreign_maquette, foreign_semester = self._curriculum(self.other, "FOREIGN")
        self.local_ue = self._unit("LOCAL", local_maquette, local_semester)
        self.foreign_ue = self._unit("FOREIGN", foreign_maquette, foreign_semester)
        foreign_year_ue = self._unit("FOREIGN-YEAR", foreign_maquette, local_semester)
        foreign_semester_ue = self._unit("FOREIGN-SEMESTER", local_maquette, foreign_semester)
        self.own = self._course("LOCAL", self.local_ue, "Zeta Quantum")
        self.inactive = self._course("INACTIVE", self.local_ue, "Alpha Quantum archived", active=False)
        self.foreign = [
            self._course("FOREIGN", self.foreign_ue, "Private Quantum foreign"),
            self._course("FOREIGN-YEAR", foreign_year_ue, "Private Quantum foreign year"),
            self._course("FOREIGN-SEMESTER", foreign_semester_ue, "Private Quantum foreign semester"),
        ]
        self.courses = [self.own, self.inactive, *self.foreign]

    def _curriculum(self, tenant, code):
        year = AnneeUniversitaire.objects.create(
            universite=tenant, libelle="2025-2026", date_debut="2025-09-01", date_fin="2026-06-30"
        )
        semester = Semestre.objects.create(
            annee_universitaire=year, numero=1, type="impair", date_debut="2025-09-01", date_fin="2026-01-31"
        )
        formation = Formation.objects.create(code=code, nom=f"Quantum programme {code}", type="licence")
        maquette = MaquetteFormation.objects.create(formation=formation, annee_universitaire=year)
        return maquette, semester

    def _unit(self, code, maquette, semester):
        return UE.objects.create(
            code=code, nom="Private teaching unit", maquette=maquette, semestre=semester, credits_ects=6
        )

    def _course(self, code, unit, name, active=True):
        ecue = ECUE.objects.create(ue=unit, code=code, nom="Private ECUE title", credits_ects=3)
        return EdxCourseMapping.objects.create(
            ecue=ecue, course_id=f"course-v1:SIS-U+{code}+sis", course_name=name, actif=active
        )

    def _responses(self):
        return (
            self.client.get(self.mappings_url),
            self.client.get(self.search_url, {"ressource": "cours", "q": "quantum"}),
        )

    def _assert_parity(self, expected):
        native, search = self._responses()
        assert native.status_code == search.status_code == 200
        assert native.data["count"] == search.data["count"] == len(expected)
        assert [row["id"] for row in native.data["results"]] == [
            mapping.pk for mapping in sorted(expected, key=lambda mapping: mapping.course_name)
        ]
        assert search.data["results"] == [
            {"id": mapping.pk, "code": mapping.course_id, "nom": mapping.course_name}
            for mapping in sorted(expected, key=lambda mapping: mapping.pk)
        ]
        for mapping in self.courses:
            detail = self.client.get(f"{self.mappings_url}{mapping.pk}/")
            assert detail.status_code == (200 if mapping in expected else 404), detail.data
            if mapping not in expected:
                for result in (native, search, detail):
                    assert mapping.course_id not in str(result.data)
                    assert mapping.course_name not in str(result.data)
            else:
                assert detail.data == next(row for row in native.data["results"] if row["id"] == mapping.pk)
        assert "Private ECUE title" not in str(search.data)

    def _assert_denied(self):
        details = [self.client.get(f"{self.mappings_url}{mapping.pk}/") for mapping in self.courses]
        for result in (*self._responses(), *details):
            assert result.status_code in (401, 403)
            assert "results" not in result.data
            for mapping in self.courses:
                assert mapping.course_id not in str(result.data)
                assert mapping.course_name not in str(result.data)

    def test_native_and_search_read_real_local_courses_including_inactive_mappings(self):
        ECUE.objects.create(ue=self.local_ue, code="UNMAPPED", nom="Quantum unmapped", credits_ects=3)
        before = list(EdxCourseMapping.objects.order_by("pk").values())
        outbox_count = OutboxEvent.objects.count()
        with patch("apps.integration.api.SyncService") as service, patch(
            "apps.integration.api.get_edx_client"
        ) as remote:
            self._assert_parity([self.own, self.inactive])
            detail_url = f"{self.mappings_url}{self.own.pk}/"
            assert resolve(detail_url).url_name == "course-mapping-detail"
            for url in (self.mappings_url, self.search_url, detail_url):
                assert self.client.post(url, {}, format="json").status_code == 405
            for method in ("put", "patch", "delete"):
                assert getattr(self.client, method)(detail_url, {}, format="json").status_code == 405
            missing = self.client.get(f"{self.mappings_url}{max(mapping.pk for mapping in self.courses) + 1}/")
            assert missing.status_code == 404
            service.assert_not_called()
            remote.assert_not_called()
        assert list(EdxCourseMapping.objects.order_by("pk").values()) == before
        assert OutboxEvent.objects.count() == outbox_count
        for term in (self.own.course_id.lower(), " zEtA qUaNtUm "):
            result = self.client.get(self.search_url, {"ressource": "cours", "q": term})
            assert result.status_code == 200
            assert result.data["results"] == [
                {"id": self.own.pk, "code": self.own.course_id, "nom": self.own.course_name}
            ]
        assert self.client.get(self.search_url, {"ressource": "cours", "q": "programme"}).data["count"] == 0

    def test_course_model_permission_does_not_replace_lms_administrator_access(self):
        permission = Permission.objects.get(content_type__app_label="integration", codename="view_edxcoursemapping")
        for role in ("enseignant", "etudiant"):
            reader = Utilisateur.objects.create_user(f"course-search-{role}", role=role, etablissement=self.tenant)
            reader.user_permissions.add(permission)
            self.client.force_authenticate(reader)
            self._assert_denied()

    def test_administrator_access_revocation_removes_every_course_identifier(self):
        self._assert_parity([self.own, self.inactive])
        self.admin.is_staff = False
        self.admin.save(update_fields=["is_staff"])
        self.client.force_authenticate(Utilisateur.objects.get(pk=self.admin.pk))
        self._assert_denied()

    def test_foreign_inactive_and_anonymous_administrators_are_denied(self):
        foreign_admin = Utilisateur.objects.create_user(
            "course-search-foreign", etablissement=self.other, is_staff=True, is_superuser=True
        )
        self.admin.is_active = False
        self.admin.save(update_fields=["is_active"])
        for user in (foreign_admin, self.admin, None):
            self.client.force_authenticate(user)
            self._assert_denied()

    def test_changed_ownership_and_deleted_mappings_disappear_without_stale_names(self):
        self._assert_parity([self.own, self.inactive])
        self.own.ecue.ue = self.foreign_ue
        self.own.ecue.save(update_fields=["ue"])
        self._assert_parity([self.inactive])
        EdxCourseMapping.objects.filter(pk=self.inactive.pk).delete()
        self._assert_parity([])

    def test_missing_public_and_inconsistent_tenant_contexts_are_denied(self):
        factory = APIRequestFactory()
        for tenant in (
            None,
            SimpleNamespace(pk=self.tenant.pk, schema_name="public"),
            SimpleNamespace(pk=self.tenant.pk, schema_name="different_schema"),
            SimpleNamespace(pk=self.tenant.pk + 100, schema_name=self.tenant.schema_name),
        ):
            for url, view, kwargs in (
                (self.mappings_url, course_mappings, {}),
                (self.search_url, AcademicSearchView.as_view(throttle_classes=[]), {}),
                (f"{self.mappings_url}{self.own.pk}/", course_mapping_detail, {"mapping_id": self.own.pk}),
            ):
                request = factory.get(url, {"ressource": "cours", "q": "quantum"})
                request.tenant = tenant
                force_authenticate(request, self.admin)
                result = view(request, **kwargs)
                assert result.status_code == 403
                assert "Quantum" not in str(result.data)
        with schema_context("public"):
            for url, view, kwargs in (
                (self.mappings_url, course_mappings, {}),
                (self.search_url, AcademicSearchView.as_view(throttle_classes=[]), {}),
                (f"{self.mappings_url}{self.own.pk}/", course_mapping_detail, {"mapping_id": self.own.pk}),
            ):
                request = factory.get(url, {"ressource": "cours", "q": "quantum"})
                request.tenant = self.tenant
                force_authenticate(request, self.admin)
                assert view(request, **kwargs).status_code == 403

    def test_native_legacy_unbound_admin_access_is_preserved_but_core_requires_membership(self):
        self.admin.etablissement = None
        self.admin.save(update_fields=["etablissement"])
        native, search = self._responses()
        assert native.status_code == 200
        assert native.data["count"] == 2
        assert search.status_code == 403
        assert "Quantum" not in str(search.data)
        assert self.client.get(f"{self.mappings_url}{self.own.pk}/").status_code == 200
        assert self.client.get(f"{self.mappings_url}{self.foreign[0].pk}/").status_code == 404
        self.admin.attributs_acces = {
            "permission_scopes": {"integration.view_edxcoursemapping": {"cours": []}}
        }
        self.admin.save(update_fields=["attributs_acces"])
        self.client.force_authenticate(Utilisateur.objects.get(pk=self.admin.pk))
        assert self.client.get(self.mappings_url).data["count"] == 0
        assert self.client.get(f"{self.mappings_url}{self.own.pk}/").status_code == 404
        assert self.client.get(self.search_url, {"ressource": "cours", "q": "quantum"}).status_code == 403

    def test_scopes_narrow_list_search_and_detail_with_intersection_and_unknown_scope_denial(self):
        for constraints, expected in (
            ({"cours": [self.own.pk]}, [self.own]),
            ({"ecues": [self.inactive.ecue_id]}, [self.inactive]),
            ({"formations": [self.local_ue.maquette.formation_id]}, [self.own, self.inactive]),
            ({"annees": [self.local_ue.semestre.annee_universitaire_id]}, [self.own, self.inactive]),
            ({"cours": [self.own.pk], "ecues": [self.inactive.ecue_id]}, []),
            ({"cours": [self.foreign[0].pk]}, []),
            ({"cours": []}, []),
            ({"ecues": "all"}, []),
            ({"unknown": [self.own.pk]}, []),
        ):
            with self.subTest(constraints=constraints):
                self.admin.attributs_acces = {
                    "permission_scopes": {"integration.view_edxcoursemapping": constraints}
                }
                self.admin.save(update_fields=["attributs_acces"])
                self.client.force_authenticate(Utilisateur.objects.get(pk=self.admin.pk))
                self._assert_parity(expected)

    def test_scope_revocation_rechecks_detail_without_model_permission_granting_admin_access(self):
        permission = Permission.objects.get(content_type__app_label="integration", codename="view_edxcoursemapping")
        self.admin.attributs_acces = {
            "permission_scopes": {"integration.view_edxcoursemapping": {"cours": [self.own.pk]}}
        }
        self.admin.save(update_fields=["attributs_acces"])
        for granted in (True, False):
            if granted:
                self.admin.user_permissions.add(permission)
            else:
                self.admin.user_permissions.remove(permission)
            self.client.force_authenticate(Utilisateur.objects.get(pk=self.admin.pk))
            self._assert_parity([self.own])
        self.admin.attributs_acces = {
            "permission_scopes": {"integration.view_edxcoursemapping": {"cours": []}}
        }
        self.admin.save(update_fields=["attributs_acces"])
        self.client.force_authenticate(Utilisateur.objects.get(pk=self.admin.pk))
        self._assert_parity([])
        self.admin.user_permissions.add(permission)
        self.admin.is_staff = False
        self.admin.save(update_fields=["is_staff"])
        self.client.force_authenticate(Utilisateur.objects.get(pk=self.admin.pk))
        self._assert_denied()

    def test_year_scope_must_cover_both_local_curriculum_and_semester_years(self):
        year = AnneeUniversitaire.objects.create(
            universite=self.tenant, libelle="2024-2025", date_debut="2024-09-01", date_fin="2025-06-30"
        )
        semester = Semestre.objects.create(
            annee_universitaire=year, numero=1, type="impair", date_debut="2024-09-01", date_fin="2025-01-31"
        )
        old_maquette = MaquetteFormation.objects.create(
            formation=self.local_ue.maquette.formation, annee_universitaire=year
        )
        mixed_year = self._unit("OLD-YEAR", old_maquette, self.local_ue.semestre)
        mixed_semester = self._unit("OLD-SEMESTER", self.local_ue.maquette, semester)
        mixed_courses = [
            self._course("OLD-YEAR", mixed_year, "Quantum old curriculum"),
            self._course("OLD-SEMESTER", mixed_semester, "Quantum old semester"),
        ]
        self.courses.extend(mixed_courses)
        for allowed, expected in (
            ([self.local_ue.semestre.annee_universitaire_id], [self.own, self.inactive]),
            ([year.pk], []),
            ([year.pk, self.local_ue.semestre.annee_universitaire_id], [self.own, self.inactive, *mixed_courses]),
        ):
            self.admin.attributs_acces = {
                "permission_scopes": {"integration.view_edxcoursemapping": {"annees": allowed}}
            }
            self.admin.save(update_fields=["attributs_acces"])
            self.client.force_authenticate(Utilisateur.objects.get(pk=self.admin.pk))
            self._assert_parity(expected)

    def test_native_ordering_and_pagination_remain_unchanged(self):
        with patch.object(PageNumberPagination, "page_size", 1):
            first = self.client.get(self.mappings_url)
            second = self.client.get(self.mappings_url, {"page": "2"})
        assert first.status_code == second.status_code == 200
        assert first.data["count"] == second.data["count"] == 2
        assert first.data["results"][0]["id"] == self.inactive.pk
        assert first.data["results"][0]["actif"] is False
        assert second.data["results"][0]["id"] == self.own.pk
        assert first.data["next"] and second.data["previous"]
        assert second.data["next"] is None

    def test_course_search_keeps_query_validation_and_bounded_pagination(self):
        for term in ("", " ", "a", "x" * 101, "quantum\n", "quantum\x7f", " " * 99 + "ab"):
            assert self.client.get(self.search_url, {"ressource": "cours", "q": term}).status_code == 400
        for index in range(50):
            self._course(f"EXTRA-{index:02}", self.local_ue, f"Quantum extra {index:02}")
        params = {"ressource": "cours", "q": "quantum"}
        default = self.client.get(self.search_url, params)
        first = self.client.get(self.search_url, {**params, "page_size": "999"})
        second = self.client.get(self.search_url, {**params, "page_size": "999", "page": "2"})
        assert default.status_code == first.status_code == second.status_code == 200
        assert default.data["count"] == first.data["count"] == second.data["count"] == 52
        assert len(default.data["results"]) == 20
        assert len(first.data["results"]) == 50
        assert len(second.data["results"]) == 2
        assert not {row["id"] for row in first.data["results"]} & {
            row["id"] for row in second.data["results"]
        }
