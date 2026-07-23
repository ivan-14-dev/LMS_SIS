"""Models for ECTS (SIS Supérieur)."""
from django.db import models
from apps.etudiants.models import Etudiant, InscriptionAdministrative
from apps.ue_ecue.models import UE
from apps.etablissement.models import AnneeUniversitaire


class BilanECTS(models.Model):
    """Bilan annuel ECTS d'un étudiant."""
    etudiant = models.ForeignKey(Etudiant, on_delete=models.CASCADE, related_name="bilans_ects")
    annee_universitaire = models.ForeignKey(
        AnneeUniversitaire, on_delete=models.CASCADE, related_name="bilans_ects"
    )
    inscription_admin = models.ForeignKey(
        InscriptionAdministrative, on_delete=models.CASCADE, related_name="bilans_ects"
    )
    credits_inscrits = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    credits_valides = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    credits_compenses = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    credits_echec = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    moyenne_ponderee = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    ues_validees = models.ManyToManyField(UE, blank=True, related_name="bilans_validees")
    ues_compensees = models.ManyToManyField(UE, blank=True, related_name="bilans_compensees")
    ues_echec = models.ManyToManyField(UE, blank=True, related_name="bilans_echec")
    date_calcul = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("etudiant", "annee_universitaire")]
        verbose_name = "Bilan ECTS"
        verbose_name_plural = "Bilans ECTS"

    def __str__(self):
        return f"Bilan {self.etudiant} - {self.annee_universitaire}"

    @property
    def taux_validation(self):
        if self.credits_inscrits == 0:
            return 0
        return (self.credits_valides / self.credits_inscrits) * 100
