"""Services for mobilite."""

from apps.etablissement.models import AnneeUniversitaire
from apps.etudiants.models import Etudiant
from apps.formations.models import Formation
from django.db.models import Q

from .models import AccordEtudes, CandidatureMobilite, ProgrammeMobilite


def formations_du_tenant(tenant_id):
    if tenant_id is None:
        return Formation.objects.none()
    return Formation.objects.filter(
        Q(departement__isnull=True) | Q(departement__faculte__universite_id=tenant_id),
        Q(ecole_doctorale__isnull=True) | Q(ecole_doctorale__universite_id=tenant_id),
    )


def annees_du_tenant(tenant_id):
    return AnneeUniversitaire.objects.filter(universite_id=tenant_id)


def etudiants_du_tenant(tenant_id):
    return Etudiant.objects.filter(universite_id=tenant_id)


def programmes_du_tenant(tenant_id):
    return ProgrammeMobilite.objects.filter(
        annee_universitaire__universite_id=tenant_id,
        formation__in=formations_du_tenant(tenant_id),
    )


def candidatures_du_tenant(tenant_id):
    return CandidatureMobilite.objects.filter(
        etudiant__universite_id=tenant_id,
        programme__in=programmes_du_tenant(tenant_id),
    )


def accords_du_tenant(tenant_id):
    return AccordEtudes.objects.filter(
        candidature__in=candidatures_du_tenant(tenant_id),
    )
