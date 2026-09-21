"""Consolidated learner/family and staff/admin portal APIs for SIS Supérieur."""

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from sis_common.authorization import permission_snapshot, request_has_business_access

from apps.portail_doyen.api import PortailDoyenViewSet
from apps.portail_enseignant.api import PortailEnseignantViewSet
from apps.portail_etudiant.api import PortailEtudiantViewSet
from apps.portail_scolarite.api import PortailScolariteViewSet


def _delegate(viewset_class, request, action_name):
    view = viewset_class()
    view.request = request
    return getattr(view, action_name)(request)


class IsApprenantFamille(IsAuthenticated):
    """Permission: portail apprenant."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        return hasattr(request.user, "etudiant_profile")


class IsStaffAdmin(IsAuthenticated):
    """Permission: portail staff/admin."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if hasattr(request.user, "etudiant_profile"):
            return False
        if request.user.is_staff or request.user.is_superuser:
            return True
        return any(
            (
                hasattr(request.user, "enseignant_profile"),
                request_has_business_access(
                    request,
                    "etudiants.view_etudiant",
                    ("scolarite", "directeur_etudes", "chef_departement", "doyen"),
                    tenant_group_codes=(
                        "academic_admin_superieur",
                        "student_manager_superieur",
                        "registration_manager_superieur",
                        "finance_manager_superieur",
                    ),
                ),
                request_has_business_access(
                    request,
                    "formations.view_formation",
                    ("doyen", "vice_doyen", "president", "vice_president"),
                    tenant_group_codes=(
                        "academic_admin_superieur",
                        "student_manager_superieur",
                        "research_manager_superieur",
                    ),
                ),
            )
        )


def _staff_mode(request):
    role = getattr(request.user, "role", "")
    if role in ("doyen", "vice_doyen", "president", "vice_president"):
        return "leadership"
    if role in ("enseignant", "chercheur"):
        return "teacher"
    if hasattr(request.user, "enseignant_profile"):
        return "teacher"
    if role in ("scolarite", "directeur_etudes", "chef_departement", "comptable"):
        return "registrar"
    if request_has_business_access(
        request,
        "formations.view_formation",
        ("doyen", "vice_doyen", "president", "vice_president"),
        tenant_group_codes=(
            "academic_admin_superieur",
            "student_manager_superieur",
            "research_manager_superieur",
        ),
    ):
        return "leadership"
    if request_has_business_access(
        request,
        "etudiants.view_etudiant",
        ("scolarite", "directeur_etudes", "chef_departement", "doyen"),
        tenant_group_codes=(
            "academic_admin_superieur",
            "student_manager_superieur",
            "registration_manager_superieur",
            "finance_manager_superieur",
        ),
    ):
        return "registrar"
    return "generic"


class PortailApprenantViewSet(viewsets.ViewSet):
    """Unified portal surface for learners."""

    permission_classes = [IsApprenantFamille]

    @action(detail=False, methods=["get"])
    def tableau_bord(self, request):
        return _delegate(PortailEtudiantViewSet, request, "tableau_bord")

    @action(detail=False, methods=["get"])
    def releves(self, request):
        return _delegate(PortailEtudiantViewSet, request, "releves")


class PortailStaffViewSet(viewsets.ViewSet):
    """Unified portal surface for staff and admins."""

    permission_classes = [IsStaffAdmin]

    @action(detail=False, methods=["get"])
    def tableau_bord(self, request):
        mode = _staff_mode(request)
        if mode == "teacher":
            return _delegate(PortailEnseignantViewSet, request, "tableau_bord")
        if mode == "leadership":
            return _delegate(PortailDoyenViewSet, request, "tableau_bord")
        if mode == "registrar":
            return _delegate(PortailScolariteViewSet, request, "tableau_bord")
        snapshot = permission_snapshot(
            request.user,
            getattr(getattr(request, "tenant", None), "configuration_academique", {}),
        )
        return Response(
            {
                "staff": {
                    "role": snapshot.get("role"),
                    "groups": snapshot.get("groups", []),
                },
                "statistiques": {},
            }
        )

    @action(detail=False, methods=["get"])
    def notes_a_saisir(self, request):
        if _staff_mode(request) == "teacher":
            return _delegate(PortailEnseignantViewSet, request, "notes_a_saisir")
        return Response([], status=200)

    @action(detail=False, methods=["get"])
    def alertes(self, request):
        if _staff_mode(request) == "registrar":
            return _delegate(PortailScolariteViewSet, request, "alertes")
        return Response([], status=200)

    @action(detail=False, methods=["get"])
    def statistiques_formations(self, request):
        if _staff_mode(request) == "leadership":
            return _delegate(PortailDoyenViewSet, request, "statistiques_formations")
        return Response([], status=200)
