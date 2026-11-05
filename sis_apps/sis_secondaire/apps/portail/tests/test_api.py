"""API tests for consolidated portail."""

from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from django.urls import resolve
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.portail.api import (
    _TenantParentPortal,
    _TenantTeacherPortal,
    PortailApprenantViewSet,
    PortailStaffViewSet,
    portal_capabilities,
)
from apps.utilisateurs.api import UtilisateursViewSet


class PortailAPITestCase(SimpleTestCase):
    def test_apprenant_routes_are_registered(self):
        assert resolve("/api/v1/portail/apprenant/tableau_bord/").url_name == "portail-apprenant-tableau-bord"
        assert resolve("/api/v1/portail/apprenant/bulletins/").url_name == "portail-apprenant-bulletins"

    def test_staff_routes_are_registered(self):
        assert resolve("/api/v1/portail/staff/tableau_bord/").url_name == "portail-staff-tableau-bord"
        assert resolve("/api/v1/portail/staff/absences_a_saisir/").url_name == "portail-staff-absences-a-saisir"

    def _call(self, viewset, action, user, tenant_id=7):
        request = APIRequestFactory().get(f"/api/v1/portail/{action}/")
        request.tenant = SimpleNamespace(pk=tenant_id, configuration_academique={})
        force_authenticate(request, user=user)
        permissions = getattr(viewset, action).kwargs.get("permission_classes", viewset.permission_classes)
        return viewset.as_view({"get": action}, throttle_classes=[], permission_classes=permissions)(request)

    def _user(self, role, *, tenant_id=7, **profiles):
        return SimpleNamespace(
            pk=12,
            role=role,
            etablissement_id=tenant_id,
            is_authenticated=True,
            is_active=True,
            is_staff=False,
            is_superuser=False,
            has_perm=lambda permission: False,
            **profiles,
        )

    @patch("apps.portail.api.current_lms_tenant")
    @patch("apps.utilisateurs.api.module_snapshot", return_value={"enabled": {}})
    @patch("apps.utilisateurs.api.permission_snapshot", return_value={"permissions": []})
    def test_account_capabilities_publish_portal_affiliations(self, _snapshot, _modules, current_tenant):
        current_tenant.side_effect = lambda request: request.tenant
        request = APIRequestFactory().get("/api/v1/utilisateurs/comptes/capabilities/")
        request.tenant = SimpleNamespace(pk=7, configuration_academique={})
        student = self._user("eleve", eleve_profile=SimpleNamespace(etablissement_id=7))
        force_authenticate(request, user=student)
        view = UtilisateursViewSet.as_view({"get": "capabilities"}, throttle_classes=[])

        response = view(request)

        assert response.status_code == 200
        assert response.data["portals"] == {"staff": False, "learner": True, "parent": False}
        assert response.data["affiliations"] == [{"kind": "learner", "active": True}]

    @patch("apps.portail.api.current_lms_tenant")
    def test_portal_capabilities_follow_role_profile_and_tenant(self, current_tenant):
        current_tenant.side_effect = lambda request: request.tenant
        request = SimpleNamespace(tenant=SimpleNamespace(pk=7, configuration_academique={}))
        denied = {"affiliations": [], "portals": {"staff": False, "learner": False, "parent": False}}
        cases = (
            (self._user("eleve", eleve_profile=SimpleNamespace(etablissement_id=7)), "learner"),
            (self._user("parent", tuteur_profile=SimpleNamespace(etablissement_id=7)), "parent"),
            (self._user("enseignant", personnel_profile=SimpleNamespace()), "staff"),
            (self._user("vie_scolaire"), "staff"),
            (self._user("eleve", tenant_id=8, eleve_profile=SimpleNamespace(etablissement_id=8)), None),
            (self._user("parent", tuteur_profile=SimpleNamespace(etablissement_id=8)), None),
            (self._user("enseignant"), None),
            (self._user("eleve"), None),
        )
        for user, kind in cases:
            request.user = user
            expected = denied if kind is None else {
                "affiliations": [{"kind": kind, "active": True}],
                "portals": {key: key == kind for key in ("staff", "learner", "parent")},
            }
            with self.subTest(role=user.role, tenant=user.etablissement_id, kind=kind):
                assert portal_capabilities(request) == expected

    @patch("apps.portail.api.current_lms_tenant")
    def test_suspended_or_invalid_tenant_has_no_portal_capabilities(self, current_tenant):
        request = SimpleNamespace(tenant=SimpleNamespace(pk=7, configuration_academique={}))
        request.user = self._user("eleve", eleve_profile=SimpleNamespace(etablissement_id=7))
        request.user.is_active = False
        denied = {"affiliations": [], "portals": {"staff": False, "learner": False, "parent": False}}
        assert portal_capabilities(request) == denied
        current_tenant.assert_not_called()
        request.user.is_active = True
        current_tenant.side_effect = PermissionDenied("invalid schema")
        assert portal_capabilities(request) == denied

    @patch("apps.portail.api.current_lms_tenant")
    @patch("apps.portail.api._delegate", return_value=Response({"owner": True}))
    def test_learner_only_own_tenant_and_role(self, delegate, current_tenant):
        current_tenant.side_effect = lambda request: request.tenant
        student = self._user("eleve", eleve_profile=SimpleNamespace(etablissement_id=7))
        assert self._call(PortailApprenantViewSet, "tableau_bord", student).status_code == 200
        assert delegate.call_args.args[0].__name__ == "PortailEleveViewSet"
        assert self._call(PortailApprenantViewSet, "bulletins", student).status_code == 200
        for outsider in (
            self._user("eleve", tenant_id=8, eleve_profile=SimpleNamespace(etablissement_id=8)),
            self._user("eleve", eleve_profile=SimpleNamespace(etablissement_id=8)),
            self._user("enseignant", eleve_profile=SimpleNamespace(etablissement_id=7)),
        ):
            assert self._call(PortailApprenantViewSet, "tableau_bord", outsider).status_code == 403
        parent = self._user("parent", tuteur_profile=SimpleNamespace(etablissement_id=7))
        assert self._call(PortailApprenantViewSet, "tableau_bord", parent).status_code == 200
        assert delegate.call_args.args[0].__name__ == "_TenantParentPortal"
        assert self._call(PortailApprenantViewSet, "bulletins", parent).status_code == 403

    @patch("apps.portail.api.current_lms_tenant")
    @patch("apps.portail.api._delegate", return_value=Response({"owner": True}))
    def test_only_assigned_teacher_is_delegated_staff_activity(self, delegate, current_tenant):
        current_tenant.side_effect = lambda request: request.tenant
        teacher = self._user("enseignant", personnel_profile=SimpleNamespace())
        assert self._call(PortailStaffViewSet, "mes_classes", teacher).status_code == 200
        assert self._call(PortailStaffViewSet, "absences_a_saisir", teacher).status_code == 200
        assert delegate.call_args.args[0].__name__ == "_TenantTeacherPortal"
        delegate.reset_mock()
        for outsider in (
            self._user("enseignant", tenant_id=8, personnel_profile=SimpleNamespace()),
            self._user("eleve", personnel_profile=SimpleNamespace()),
            self._user("personnel_administratif", personnel_profile=SimpleNamespace()),
        ):
            assert self._call(PortailStaffViewSet, "mes_classes", outsider).status_code == 403
        delegate.assert_not_called()

    @patch("apps.portail.api.current_lms_tenant")
    def test_admin_with_personnel_profile_cannot_see_teacher_classes(self, current_tenant):
        current_tenant.side_effect = lambda request: request.tenant
        admin = self._user("direction", personnel_profile=SimpleNamespace())
        admin.is_staff = True
        response = self._call(PortailStaffViewSet, "mes_classes", admin)
        assert response.status_code == 403

    @patch("apps.portail.api.current_lms_tenant", side_effect=PermissionDenied())
    def test_public_or_invalid_schema_is_refused(self, current_tenant):
        student = self._user("eleve", eleve_profile=SimpleNamespace(etablissement_id=7))
        assert self._call(PortailApprenantViewSet, "tableau_bord", student).status_code == 403

    def test_assignments_and_parent_links_are_scoped_before_serializing(self):
        teacher = _TenantTeacherPortal()
        teacher.request = SimpleNamespace(tenant=SimpleNamespace(pk=7))
        query = teacher._affectations_queryset(SimpleNamespace(pk=12)).query
        sql, params = query.sql_with_params()
        assert 12 in params and params.count(7) >= 3
        assert "annee_scolaire" in sql and "matiere" in sql and "classe" in sql

        own = SimpleNamespace(annee_scolaire_id=1)
        other_year = SimpleNamespace(annee_scolaire_id=2)
        assignment = SimpleNamespace(
            annee_scolaire_id=1,
            classes=SimpleNamespace(all=lambda: [own, other_year]),
        )
        with patch.object(teacher, "_affectations_queryset", return_value=[assignment]):
            request = SimpleNamespace(user=SimpleNamespace(personnel_profile=SimpleNamespace()))
            assert list(teacher._assigned_classes(request)) == [(assignment, own)]

        parent = _TenantParentPortal()
        parent.request = SimpleNamespace(tenant=SimpleNamespace(pk=7))
        links = parent._authorized_links(
            SimpleNamespace(
                user=SimpleNamespace(tuteur_profile=SimpleNamespace(pk=12)),
                tenant=SimpleNamespace(pk=7),
            )
        )
        sql, params = links.query.sql_with_params()
        assert 12 in params and params.count(7) == 2
        assert "etablissement_id" in sql
