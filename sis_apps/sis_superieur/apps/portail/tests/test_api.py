"""API tests for consolidated portail."""

from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from django.urls import resolve
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.portail.api import _TenantTeacherPortal, PortailApprenantViewSet, PortailStaffViewSet, portal_capabilities
from apps.utilisateurs.api import UtilisateursViewSet


class PortailAPITestCase(SimpleTestCase):
    def test_apprenant_routes_are_registered(self):
        assert resolve("/api/v1/portail/apprenant/tableau_bord/").url_name == "portail-apprenant-tableau-bord"
        assert resolve("/api/v1/portail/apprenant/releves/").url_name == "portail-apprenant-releves"

    def test_staff_routes_are_registered(self):
        assert resolve("/api/v1/portail/staff/tableau_bord/").url_name == "portail-staff-tableau-bord"
        assert (
            resolve("/api/v1/portail/staff/statistiques_formations/").url_name
            == "portail-staff-statistiques-formations"
        )

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
        teacher = self._user("enseignant", enseignant_profile=SimpleNamespace())
        force_authenticate(request, user=teacher)
        view = UtilisateursViewSet.as_view({"get": "capabilities"}, throttle_classes=[])

        response = view(request)

        assert response.status_code == 200
        assert response.data["portals"] == {"staff": True, "learner": False, "parent": False}
        assert response.data["affiliations"] == [{"kind": "staff", "active": True}]

    @patch("apps.portail.api.current_lms_tenant")
    def test_portal_capabilities_follow_role_profile_and_tenant(self, current_tenant):
        current_tenant.side_effect = lambda request: request.tenant
        request = SimpleNamespace(tenant=SimpleNamespace(pk=7, configuration_academique={}))
        denied = {"affiliations": [], "portals": {"staff": False, "learner": False, "parent": False}}
        cases = (
            (self._user("etudiant", etudiant_profile=SimpleNamespace(universite_id=7)), "learner"),
            (self._user("doctorant", etudiant_profile=SimpleNamespace(universite_id=7)), "learner"),
            (self._user("enseignant", enseignant_profile=SimpleNamespace()), "staff"),
            (self._user("scolarite"), "staff"),
            (self._user("etudiant", tenant_id=8, etudiant_profile=SimpleNamespace(universite_id=8)), None),
            (self._user("etudiant", etudiant_profile=SimpleNamespace(universite_id=8)), None),
            (self._user("parent"), None),
            (self._user("enseignant"), None),
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
        request.user = self._user("etudiant", etudiant_profile=SimpleNamespace(universite_id=7))
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
        student = self._user("etudiant", etudiant_profile=SimpleNamespace(universite_id=7))
        assert self._call(PortailApprenantViewSet, "releves", student).status_code == 200
        assert delegate.call_args.args[0].__name__ == "PortailEtudiantViewSet"
        for outsider in (
            self._user("etudiant", tenant_id=8, etudiant_profile=SimpleNamespace(universite_id=8)),
            self._user("etudiant", etudiant_profile=SimpleNamespace(universite_id=8)),
            self._user("enseignant", etudiant_profile=SimpleNamespace(universite_id=7)),
        ):
            assert self._call(PortailApprenantViewSet, "releves", outsider).status_code == 403
        doctorant = self._user("doctorant", etudiant_profile=SimpleNamespace(universite_id=7))
        assert self._call(PortailApprenantViewSet, "releves", doctorant).status_code == 200

    @patch("apps.portail.api.current_lms_tenant")
    @patch("apps.portail.api._delegate", return_value=Response({"owner": True}))
    def test_only_teacher_is_delegated_assigned_activity(self, delegate, current_tenant):
        current_tenant.side_effect = lambda request: request.tenant
        teacher = self._user("enseignant", enseignant_profile=SimpleNamespace())
        assert self._call(PortailStaffViewSet, "notes_a_saisir", teacher).status_code == 200
        assert delegate.call_args.args[0].__name__ == "_TenantTeacherPortal"
        delegate.reset_mock()
        for outsider in (
            self._user("enseignant", tenant_id=8, enseignant_profile=SimpleNamespace()),
            self._user("etudiant", enseignant_profile=SimpleNamespace()),
            self._user("personnel_administratif", enseignant_profile=SimpleNamespace()),
        ):
            assert self._call(PortailStaffViewSet, "notes_a_saisir", outsider).status_code == 403
        delegate.assert_not_called()

    @patch("apps.portail.api.current_lms_tenant")
    def test_admin_with_teacher_profile_cannot_see_teacher_notes(self, current_tenant):
        current_tenant.side_effect = lambda request: request.tenant
        admin = self._user("doyen", enseignant_profile=SimpleNamespace())
        admin.is_staff = True
        response = self._call(PortailStaffViewSet, "notes_a_saisir", admin)
        assert response.status_code == 403

    @patch("apps.portail.api.current_lms_tenant")
    @patch("apps.portail.api._delegate", return_value=Response({"owner": True}))
    def test_staff_specialized_actions_do_not_cross_roles(self, delegate, current_tenant):
        current_tenant.side_effect = lambda request: request.tenant
        registrar = self._user("scolarite")
        leader = self._user("doyen")
        assert self._call(PortailStaffViewSet, "alertes", registrar).status_code == 200
        assert delegate.call_args.args[0].__name__ == "PortailScolariteViewSet"
        assert self._call(PortailStaffViewSet, "statistiques_formations", registrar).status_code == 403
        assert self._call(PortailStaffViewSet, "statistiques_formations", leader).status_code == 200
        assert delegate.call_args.args[0].__name__ == "PortailDoyenViewSet"
        assert self._call(PortailStaffViewSet, "alertes", leader).status_code == 403

    @patch("apps.portail.api.current_lms_tenant", side_effect=PermissionDenied())
    def test_public_or_invalid_schema_is_refused(self, current_tenant):
        student = self._user("etudiant", etudiant_profile=SimpleNamespace(universite_id=7))
        assert self._call(PortailApprenantViewSet, "releves", student).status_code == 403

    def test_teacher_assignment_query_limits_year_and_university(self):
        teacher = _TenantTeacherPortal()
        teacher.request = SimpleNamespace(tenant=SimpleNamespace(pk=7))
        sql, params = teacher._affectations_queryset(SimpleNamespace(pk=12)).query.sql_with_params()
        assert 12 in params and params.count(7) >= 3
        assert "annee_universitaire" in sql and "formation" in sql and "semestre" in sql
