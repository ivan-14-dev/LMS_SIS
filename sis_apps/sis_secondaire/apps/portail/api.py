"""Consolidated learner/family and staff/admin portal APIs for SIS Secondaire."""

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from sis_common.authorization import permission_snapshot, request_has_business_access

from apps.portail_eleve.api import PortailEleveViewSet
from apps.portail_enseignant.api import PortailEnseignantViewSet
from apps.portail_parent.api import PortailParentViewSet


def _delegate(viewset_class, request, action_name):
    view = viewset_class()
    view.request = request
    return getattr(view, action_name)(request)


class IsApprenantFamille(IsAuthenticated):
    """Permission: portail apprenant/famille."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        return hasattr(request.user, "eleve_profile") or hasattr(
            request.user, "tuteur_profile"
        )


class IsStaffAdmin(IsAuthenticated):
    """Permission: portail staff/admin."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if hasattr(request.user, "eleve_profile") or hasattr(request.user, "tuteur_profile"):
            return False
        if request.user.is_staff or request.user.is_superuser:
            return True
        if hasattr(request.user, "personnel_profile"):
            return True
        return request_has_business_access(
            request,
            "notes.view_evaluation",
            (
                "enseignant",
                "vie_scolaire",
                "direction",
                "proviseur",
                "principal",
                "cpe",
                "pp",
            ),
            tenant_group_codes=(
                "class_manager_secondary",
                "class_council_manager_secondary",
                "exam_manager_secondary",
            ),
        )


class PortailApprenantViewSet(viewsets.ViewSet):
    """Unified portal surface for learners and parents."""

    permission_classes = [IsApprenantFamille]

    @action(detail=False, methods=["get"])
    def tableau_bord(self, request):
        if hasattr(request.user, "eleve_profile"):
            return _delegate(PortailEleveViewSet, request, "tableau_bord")
        return _delegate(PortailParentViewSet, request, "tableau_bord")

    @action(detail=False, methods=["get"])
    def bulletins(self, request):
        if hasattr(request.user, "eleve_profile"):
            return _delegate(PortailEleveViewSet, request, "bulletins")
        return Response([], status=200)


class PortailStaffViewSet(viewsets.ViewSet):
    """Unified portal surface for staff and admins."""

    permission_classes = [IsStaffAdmin]

    @action(detail=False, methods=["get"])
    def tableau_bord(self, request):
        if hasattr(request.user, "personnel_profile"):
            return _delegate(PortailEnseignantViewSet, request, "tableau_bord")
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
    def mes_classes(self, request):
        if hasattr(request.user, "personnel_profile"):
            return _delegate(PortailEnseignantViewSet, request, "mes_classes")
        return Response([], status=200)

    @action(detail=False, methods=["get"])
    def absences_a_saisir(self, request):
        if hasattr(request.user, "personnel_profile"):
            return _delegate(PortailEnseignantViewSet, request, "absences_a_saisir")
        return Response([], status=200)
