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
    etablissement = models.ForeignKey("etablissement.Etablissement", on_delete=models.PROTECT, related_name="+")
    curriculum = models.ForeignKey("classes.Classe", on_delete=models.PROTECT, related_name="+")


class RevisionProgrammePratique(RevisionProgrammePratiqueBase):
    pass


class DossierPratique(DossierPratiqueBase):
    etablissement = models.ForeignKey("etablissement.Etablissement", on_delete=models.PROTECT, related_name="+")
    apprenant = models.ForeignKey("eleves.Eleve", on_delete=models.PROTECT, related_name="+")
    inscription = models.ForeignKey("eleves.Inscription", on_delete=models.PROTECT, related_name="+")


class HeurePratique(HeurePratiqueBase):
    apprenant = models.ForeignKey("eleves.Eleve", on_delete=models.PROTECT, related_name="+")


class DecisionHeurePratique(DecisionHeurePratiqueBase):
    pass


class EvaluationCompetencePratique(EvaluationCompetencePratiqueBase):
    pass


class AuditPratique(AuditPratiqueBase):
    pass
