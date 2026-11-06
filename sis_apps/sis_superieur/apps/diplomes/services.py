"""Academic prerequisites for diploma issuance."""

from apps.etudiants.models import InscriptionAdministrative
from apps.jurys.models import DecisionGlobale


def has_issuance_prerequisite(*, etudiant, diplome, annee_universitaire, date_obtention, tenant):
    """Require a validated enrollment and a closed final-semester jury admission."""
    if (
        tenant is None
        or etudiant.universite_id != tenant.pk
        or annee_universitaire.universite_id != tenant.pk
    ):
        return False

    formation_id = diplome.formation_id
    if not InscriptionAdministrative.objects.filter(
        etudiant_id=etudiant.pk,
        annee_universitaire_id=annee_universitaire.pk,
        formation_id=formation_id,
        statut="validee",
    ).exists():
        return False

    return DecisionGlobale.objects.filter(
        etudiant_id=etudiant.pk,
        decision__in=("admis", "admis_mention"),
        deliberation__date_cloture__date__lte=date_obtention,
        deliberation__jury__statut="cloture",
        deliberation__jury__formation_id=formation_id,
        deliberation__jury__semestre__annee_universitaire_id=annee_universitaire.pk,
        deliberation__jury__semestre__annee_universitaire__universite_id=tenant.pk,
        deliberation__jury__semestre__numero=diplome.formation.nb_semestres,
    ).exists()
