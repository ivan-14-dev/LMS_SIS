"""Consolidated learner/family and staff/admin portal APIs for SIS Secondaire."""

from apps.portail_eleve.api import PortailEleveViewSet
from apps.portail_enseignant.api import PortailEnseignantViewSet
from apps.portail_parent.api import PortailParentViewSet
from apps.classes.models import Classe
from apps.emplois_du_temps.models import Creneau
from apps.enseignants.models import AffectationEnseignant
from apps.presences.models import Appel
from django.db.models import F, Prefetch
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from sis_common.authorization import permission_snapshot, request_has_business_access
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
        classes = Classe.objects.filter(
            etablissement_id=tenant_id,
            annee_scolaire__etablissement_id=tenant_id,
            niveau__etablissement_id=tenant_id,
        )
        return (
            AffectationEnseignant.objects.filter(
                enseignant_id=enseignant.pk,
                annee_scolaire__etablissement_id=tenant_id,
                matiere__etablissement_id=tenant_id,
                classes__in=classes,
                classes__annee_scolaire_id=F("annee_scolaire_id"),
            )
            .distinct()
            .select_related("matiere", "annee_scolaire")
            .prefetch_related(Prefetch("classes", queryset=classes.select_related("niveau")))
        )

    def _assigned_classes(self, request):
        for assignment in self._affectations_queryset(request.user.personnel_profile):
            for classe in assignment.classes.all():
                if classe.annee_scolaire_id == assignment.annee_scolaire_id:
                    yield assignment, classe

    def tableau_bord(self, request):
        enseignant = request.user.personnel_profile
        classes = []
        total_eleves = 0
        for assignment, classe in self._assigned_classes(request):
            count = classe.eleves_actuels.filter(
                etablissement_id=request.tenant.pk,
                user__etablissement_id=request.tenant.pk,
            ).count()
            total_eleves += count
            classes.append({
                "classe_id": classe.id,
                "classe_nom": classe.nom,
                "niveau": classe.niveau.libelle,
                "matiere": assignment.matiere.nom,
                "annee_scolaire": assignment.annee_scolaire.libelle,
                "nb_eleves": count,
                "heures_semaine": float(assignment.heures_semaine),
            })
        tenant_id = request.tenant.pk
        classes_pp = [
            {"id": classe.id, "nom": classe.nom, "niveau": classe.niveau.libelle if classe.niveau else None}
            for classe in Classe.objects.filter(
                prof_principal=request.user,
                etablissement_id=tenant_id,
                annee_scolaire__etablissement_id=tenant_id,
                niveau__etablissement_id=tenant_id,
            ).select_related("niveau").order_by("niveau__ordre", "nom")
        ]
        return Response({
            "enseignant": {
                "nom": enseignant.user.get_full_name(),
                "matricule": enseignant.matricule,
                "statut": enseignant.statut,
            },
            "classes": classes,
            "classes_pp": classes_pp,
            "statistiques": {
                "nb_affectations": self._affectations_queryset(enseignant).count(),
                "nb_classes": len({item["classe_id"] for item in classes}),
                "nb_eleves_total": total_eleves,
            },
        })

    def mes_classes(self, request):
        return Response([
            {
                "id": classe.id,
                "nom": classe.nom,
                "niveau": classe.niveau.libelle,
                "matiere": assignment.matiere.nom,
                "nb_eleves": classe.eleves_actuels.filter(
                    etablissement_id=request.tenant.pk,
                    user__etablissement_id=request.tenant.pk,
                ).count(),
                "heures_semaine": float(assignment.heures_semaine),
                "annee_scolaire": assignment.annee_scolaire.libelle,
            }
            for assignment, classe in self._assigned_classes(request)
        ])

    def absences_a_saisir(self, request):
        today = timezone.localdate()
        tenant_id = request.tenant.pk
        affectations = self._affectations_queryset(request.user.personnel_profile)
        creneaux = Creneau.objects.filter(
            enseignant=request.user.personnel_profile,
            jour=today.weekday() + 1,
            actif=True,
            classe__etablissement_id=tenant_id,
            classe__annee_scolaire__etablissement_id=tenant_id,
            matiere__etablissement_id=tenant_id,
            classe__affectations_enseignant__in=affectations,
            classe__affectations_enseignant__matiere_id=F("matiere_id"),
            classe__affectations_enseignant__annee_scolaire_id=F("classe__annee_scolaire_id"),
        ).distinct().select_related("classe", "matiere")
        return Response([
            {
                "creneau_id": creneau.id,
                "classe": creneau.classe.nom,
                "matiere": creneau.matiere.nom,
                "heure": str(creneau.heure_debut),
            }
            for creneau in creneaux
            if not Appel.objects.filter(creneau=creneau, date=today).exists()
        ])


class _TenantParentPortal(PortailParentViewSet):
    """Keep the direct parent portal's tenant and ABAC restrictions."""


class IsApprenantFamille(IsAuthenticated):
    """Permission: portail apprenant/famille."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        tenant = _portal_tenant(request)
        if tenant is None:
            return False
        if request.user.role == "eleve":
            return (
                hasattr(request.user, "eleve_profile")
                and request.user.eleve_profile.etablissement_id == tenant.pk
            )
        if request.user.role == "parent":
            return (
                hasattr(request.user, "tuteur_profile")
                and request.user.tuteur_profile.etablissement_id == tenant.pk
            )
        return False


class IsStaffAdmin(IsAuthenticated):
    """Permission: portail staff/admin."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if _portal_tenant(request) is None:
            return False
        if request.user.role in ("eleve", "parent"):
            return False
        if request.user.role == "enseignant":
            return hasattr(request.user, "personnel_profile")
        if request.user.is_staff or request.user.is_superuser:
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


class IsElevePortal(IsApprenantFamille):
    def has_permission(self, request, view):
        return super().has_permission(request, view) and request.user.role == "eleve"


class IsParentPortal(IsApprenantFamille):
    def has_permission(self, request, view):
        return super().has_permission(request, view) and request.user.role == "parent"


class IsTeacherPortal(IsStaffAdmin):
    def has_permission(self, request, view):
        return (
            super().has_permission(request, view)
            and request.user.role == "enseignant"
            and hasattr(request.user, "personnel_profile")
        )


def portal_capabilities(request):
    """Expose the same tenant-bound entry permissions as the portal views."""
    portals = {"staff": False, "learner": False, "parent": False}
    user = request.user
    if user.is_authenticated and user.is_active:
        try:
            apprenant = IsApprenantFamille().has_permission(request, None)
            portals["staff"] = IsStaffAdmin().has_permission(request, None)
            portals["learner"] = apprenant and user.role == "eleve"
            portals["parent"] = apprenant and user.role == "parent"
        except PermissionDenied:
            portals = {"staff": False, "learner": False, "parent": False}
    return {
        "affiliations": [{"kind": kind, "active": True} for kind, allowed in portals.items() if allowed],
        "portals": portals,
    }


class PortailApprenantViewSet(viewsets.ViewSet):
    """Unified portal surface for learners and parents."""

    permission_classes = [IsApprenantFamille]

    @action(detail=False, methods=["get"])
    def tableau_bord(self, request):
        if request.user.role == "eleve":
            return _delegate(PortailEleveViewSet, request, "tableau_bord")
        return _delegate(_TenantParentPortal, request, "tableau_bord")

    @action(detail=False, methods=["get"], permission_classes=[IsElevePortal])
    def bulletins(self, request):
        return _delegate(PortailEleveViewSet, request, "bulletins")

    @action(detail=False, methods=["get"], permission_classes=[IsParentPortal])
    def dossier_enfant(self, request):
        return _delegate(_TenantParentPortal, request, "dossier_enfant")


class PortailStaffViewSet(viewsets.ViewSet):
    """Unified portal surface for staff and admins."""

    permission_classes = [IsStaffAdmin]

    @action(detail=False, methods=["get"])
    def tableau_bord(self, request):
        if request.user.role == "enseignant" and hasattr(request.user, "personnel_profile"):
            return _delegate(_TenantTeacherPortal, request, "tableau_bord")
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
    def mes_classes(self, request):
        return _delegate(_TenantTeacherPortal, request, "mes_classes")

    @action(detail=False, methods=["get"], permission_classes=[IsTeacherPortal])
    def absences_a_saisir(self, request):
        return _delegate(_TenantTeacherPortal, request, "absences_a_saisir")
