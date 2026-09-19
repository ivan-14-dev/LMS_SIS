"""Models for rattrapages (SIS Supérieur)."""

from apps.etudiants.models import Etudiant
from apps.examens.models import SessionExamen
from apps.ue_ecue.models import ECUE
from django.db import models


class InscriptionRattrapage(models.Model):
    """Inscription d'un étudiant à un rattrapage."""

    STATUT_CHOICES = [
        ("inscrit", "Inscrit"),
        ("desiste", "Désisté"),
        ("passe", "Passé"),
        ("absent", "Absent"),
    ]
    etudiant = models.ForeignKey(
        Etudiant, on_delete=models.CASCADE, related_name="inscriptions_rattrapage"
    )
    ecue = models.ForeignKey(ECUE, on_delete=models.CASCADE, related_name="rattrapages")
    session_rattrapage = models.ForeignKey(
        SessionExamen, on_delete=models.CASCADE, related_name="inscriptions_rattrapage"
    )
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default="inscrit")
    date_inscription = models.DateTimeField(auto_now_add=True)
    note = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    date_echeance_inscription = models.DateField()

    class Meta:
        unique_together = [("etudiant", "ecue", "session_rattrapage")]
        verbose_name = "Inscription rattrapage"
        verbose_name_plural = "Inscriptions rattrapage"

    def __str__(self):
        return f"Rattrapage {self.etudiant} - {self.ecue}"
