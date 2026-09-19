"""Models for bulletins (SIS Secondaire)."""

from apps.classes.models import Matiere
from apps.eleves.models import Eleve
from apps.etablissement.models import Periode
from django.db import models


class AppreciationMatiere(models.Model):
    """Appréciation par matière d'un élève sur un bulletin."""

    eleve = models.ForeignKey(
        Eleve, on_delete=models.CASCADE, related_name="appreciations_matiere"
    )
    matiere = models.ForeignKey(
        Matiere, on_delete=models.CASCADE, related_name="appreciations"
    )
    periode = models.ForeignKey(
        Periode, on_delete=models.CASCADE, related_name="appreciations"
    )
    appreciation = models.TextField()
    moyenne_matiere = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    moyenne_classe = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    rang = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("eleve", "matiere", "periode")]
        verbose_name = "Appréciation par matière"
        verbose_name_plural = "Appréciations par matière"

    def __str__(self):
        return f"{self.eleve} - {self.matiere} - {self.periode}"
