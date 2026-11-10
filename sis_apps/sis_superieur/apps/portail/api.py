"""Consolidated learner/family and staff/admin portal APIs for SIS Supérieur."""

from apps.enseignants.models import AffectationEnseignement
from apps.notes.models import Evaluation
from apps.portail_doyen.api import PortailDoyenViewSet
from apps.portail_enseignant.api import PortailEnseignantViewSet
from apps.portail_etudiant.api import PortailEtudiantViewSet
from apps.portail_scolarite.api import PortailScolariteViewSet
from django.db.models import Count, F, Q
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from sis_common.authorization import permission_snapshot, request_has_business_access
from sis_common.learner_timetable import personal_timetable
from sis_common.lms_tenants import current_lms_tenant


def _delegate(viewset_class, request, action_name):
    view = viewset_class()
    view.request = request
    return getattr(view, action_name)(request)


def _portal_tenant(request):
    tenant = current_lms_tenant(request)
    if request.user.etablissement_id != tenant.pk:
        return None
    return tenant


class _TenantTeacherPortal(PortailEnseignantViewSet):
    def _affectations_queryset(self, enseignant):
        tenant_id = self.request.tenant.pk
        return (
            AffectationEnseignement.objects.filter(
                enseignant_id=enseignant.pk,
                annee_universitaire__universite_id=tenant_id,
            )
            .filter(
                Q(
                    ecue__ue__maquette__formation__departement__faculte__universite_id=tenant_id,
                    ecue__ue__semestre__annee_universitaire_id=F("annee_universitaire_id"),
                )
                | Q(
                    ecue__isnull=True,
                    ue__maquette__formation__departement__faculte__universite_id=tenant_id,
                    ue__semestre__annee_universitaire_id=F("annee_universitaire_id"),
                )
            )
            .select_related(
                "ecue__ue__maquette__formation__departement",
                "ue__maquette__formation__departement",
                "annee_universitaire",
            )
        )

    def tableau_bord(self, request):
        enseignant = request.user.enseignant_profile
        assignments = self._affectations_queryset(enseignant).filter(annee_universitaire__en_cours=True)
        cours = []
        departements = set()
        for assignment in assignments:
            ecue = assignment.ecue
            ue = assignment.ue or (ecue.ue if ecue else None)
            formation = ue.maquette.formation
            if formation.departement:
                departements.add(formation.departement.nom)
            cours.append(
                {
                    "affectation_id": assignment.id,
                    "ecue_id": ecue.id if ecue else None,
                    "ecue_nom": ecue.nom if ecue else None,
                    "ue": ue.nom,
                    "formation": formation.nom,
                    "type": assignment.type_enseignement,
                    "heures": float(assignment.heures) if assignment.heures is not None else None,
                }
            )
        return Response(
            {
                "enseignant": {
                    "nom": enseignant.user.get_full_name(),
                    "corps": enseignant.corps,
                    "laboratoire": enseignant.laboratoire.nom if enseignant.laboratoire else None,
                    "departements": sorted(departements),
                },
                "cours_semestre": cours,
                "statistiques": {
                    "nb_cours": len(cours),
                    "heures_total": sum(item["heures"] or 0 for item in cours),
                },
            }
        )

    def notes_a_saisir(self, request):
        assignments = self._affectations_queryset(request.user.enseignant_profile)
        allowed = Q()
        for assignment in assignments:
            ecue_ids = [assignment.ecue_id] if assignment.ecue_id else assignment.ue.ecues.values_list("id", flat=True)
            allowed |= Q(
                ecue_id__in=ecue_ids,
                semestre__annee_universitaire_id=assignment.annee_universitaire_id,
            )
        evaluations = (
            Evaluation.objects.filter(enseignant=request.user)
            .filter(allowed if allowed else Q(pk__in=[]))
            .select_related("ecue__ue", "semestre")
            .annotate(notes_saisies=Count("notes"))
            .order_by("-date")[:25]
        )
        return Response(
            [
                {
                    "evaluation_id": evaluation.id,
                    "ecue_id": evaluation.ecue.id,
                    "ecue_nom": evaluation.ecue.nom,
                    "semestre": str(evaluation.semestre),
                    "titre": evaluation.titre,
                    "modalite": evaluation.modalite,
                    "date": evaluation.date.isoformat(),
                    "notes_saisies": evaluation.notes_saisies,
                }
                for evaluation in evaluations
            ]
        )


class IsApprenantFamille(IsAuthenticated):
    """Permission: portail apprenant."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        tenant = _portal_tenant(request)
        return (
            tenant is not None
            and request.user.role in ("etudiant", "doctorant")
            and hasattr(request.user, "etudiant_profile")
            and request.user.etudiant_profile.universite_id == tenant.pk
        )


class IsStaffAdmin(IsAuthenticated):
    """Permission: portail staff/admin."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if _portal_tenant(request) is None:
            return False
        if request.user.role in ("etudiant", "doctorant", "parent"):
            return False
        if request.user.role in ("enseignant", "chercheur"):
            return hasattr(request.user, "enseignant_profile")
        if request.user.is_staff or request.user.is_superuser:
            return True
        return _has_registrar_access(request) or _has_leadership_access(request)


def _has_registrar_access(request):
    return request_has_business_access(
        request,
        "etudiants.view_etudiant",
        ("scolarite", "directeur_etudes", "chef_departement", "doyen"),
        tenant_group_codes=(
            "academic_admin_superieur",
            "student_manager_superieur",
            "registration_manager_superieur",
            "finance_manager_superieur",
        ),
    )


def _has_leadership_access(request):
    return request_has_business_access(
        request,
        "formations.view_formation",
        ("doyen", "vice_doyen", "president", "vice_president"),
        tenant_group_codes=(
            "academic_admin_superieur",
            "student_manager_superieur",
            "research_manager_superieur",
        ),
    )


def _staff_mode(request):
    role = getattr(request.user, "role", "")
    if role in ("enseignant", "chercheur") and hasattr(request.user, "enseignant_profile"):
        return "teacher"
    if role in ("doyen", "vice_doyen", "president", "vice_president") and _has_leadership_access(request):
        return "leadership"
    if role in ("scolarite", "directeur_etudes", "chef_departement", "comptable") and _has_registrar_access(request):
        return "registrar"
    if _has_leadership_access(request):
        return "leadership"
    if _has_registrar_access(request):
        return "registrar"
    return "generic"


class IsTeacherPortal(IsStaffAdmin):
    def has_permission(self, request, view):
        return (
            super().has_permission(request, view)
            and request.user.role in ("enseignant", "chercheur")
            and hasattr(request.user, "enseignant_profile")
        )


class IsRegistrarPortal(IsStaffAdmin):
    def has_permission(self, request, view):
        return super().has_permission(request, view) and _staff_mode(request) == "registrar"


class IsLeadershipPortal(IsStaffAdmin):
    def has_permission(self, request, view):
        return super().has_permission(request, view) and _staff_mode(request) == "leadership"


def portal_capabilities(request):
    """Expose the same tenant-bound entry permissions as the portal views."""
    portals = {"staff": False, "learner": False, "parent": False}
    user = request.user
    if user.is_authenticated and user.is_active:
        try:
            portals["learner"] = IsApprenantFamille().has_permission(request, None)
            portals["staff"] = IsStaffAdmin().has_permission(request, None)
        except PermissionDenied:
            portals = {"staff": False, "learner": False, "parent": False}
    return {
        "affiliations": [{"kind": kind, "active": True} for kind, allowed in portals.items() if allowed],
        "portals": portals,
    }


class PortailApprenantViewSet(viewsets.ViewSet):
    """Unified portal surface for learners."""

    permission_classes = [IsApprenantFamille]

    @action(detail=False, methods=["get"])
    def tableau_bord(self, request):
        return _delegate(PortailEtudiantViewSet, request, "tableau_bord")

    @action(detail=False, methods=["get"])
    def releves(self, request):
        return _delegate(PortailEtudiantViewSet, request, "releves")

    @action(detail=False, methods=["get"])
    def emploi_du_temps(self, request):
        return Response(personal_timetable(request))


class PortailStaffViewSet(viewsets.ViewSet):
    """Unified portal surface for staff and admins."""

    permission_classes = [IsStaffAdmin]

    @action(detail=False, methods=["get"])
    def tableau_bord(self, request):
        mode = _staff_mode(request)
        if mode == "teacher":
            return _delegate(_TenantTeacherPortal, request, "tableau_bord")
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

    @action(detail=False, methods=["get"], permission_classes=[IsTeacherPortal])
    def notes_a_saisir(self, request):
        return _delegate(_TenantTeacherPortal, request, "notes_a_saisir")

    @action(detail=False, methods=["get"], permission_classes=[IsRegistrarPortal])
    def alertes(self, request):
        return _delegate(PortailScolariteViewSet, request, "alertes")

    @action(detail=False, methods=["get"], permission_classes=[IsLeadershipPortal])
    def statistiques_formations(self, request):
        return _delegate(PortailDoyenViewSet, request, "statistiques_formations")
