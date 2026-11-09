from django.db import models

from sis_common.practical_models import (
    AuditPratiqueBase,
    DecisionHeurePratiqueBase,
    DossierPratiqueBase,
    EvaluationCompetencePratiqueBase,
    HeurePratiqueBase,
    ProgrammePratiqueBase,
    RevisionProgrammePratiqueBase,
)


class ProgrammePratique(ProgrammePratiqueBase):
    etablissement = models.ForeignKey("etablissement.Universite", on_delete=models.PROTECT, related_name="+")
    curriculum = models.ForeignKey("formations.Formation", on_delete=models.PROTECT, related_name="+")


class RevisionProgrammePratique(RevisionProgrammePratiqueBase):
    pass


class DossierPratique(DossierPratiqueBase):
    etablissement = models.ForeignKey("etablissement.Universite", on_delete=models.PROTECT, related_name="+")
    apprenant = models.ForeignKey("etudiants.Etudiant", on_delete=models.PROTECT, related_name="+")
    inscription = models.ForeignKey("etudiants.InscriptionAdministrative", on_delete=models.PROTECT, related_name="+")
    contact_entreprise = models.ForeignKey("entreprises.ContactEntreprise", on_delete=models.PROTECT, related_name="+", null=True)


class HeurePratique(HeurePratiqueBase):
    apprenant = models.ForeignKey("etudiants.Etudiant", on_delete=models.PROTECT, related_name="+")


class DecisionHeurePratique(DecisionHeurePratiqueBase):
    pass


class EvaluationCompetencePratique(EvaluationCompetencePratiqueBase):
    pass


class AuditPratique(AuditPratiqueBase):
    pass
