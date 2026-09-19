"""Models for salles (SIS Secondaire)."""

from apps.etablissement.models import Etablissement
from django.db import models


class Salle(models.Model):
    """Salle de classe / laboratoire / gymnase."""

    TYPE_CHOICES = [
        ("salle_classique", "Salle de classe"),
        ("laboratoire", "Laboratoire"),
        ("salle_info", "Salle informatique"),
        ("gymnase", "Gymnase"),
        ("amphi", "Amphithéâtre"),
        ("bibliotheque", "Bibliothèque"),
        ("cdi", "CDI"),
        ("reunion", "Salle de réunion"),
    ]
    etablissement = models.ForeignKey(
        Etablissement, on_delete=models.CASCADE, related_name="salles"
    )
    nom = models.CharField(max_length=100)
    code = models.CharField(max_length=20)
    batiment = models.CharField(max_length=100, blank=True)
    etage = models.CharField(max_length=20, blank=True)
    capacite = models.PositiveIntegerField(default=30)
    type = models.CharField(
        max_length=30, choices=TYPE_CHOICES, default="salle_classique"
    )
    equipements = models.JSONField(
        default=list, blank=True, help_text='["projecteur", "tableau_interactif"]'
    )
    accessible_pm = models.BooleanField(
        default=True, help_text="Accessible personne mobilité réduite"
    )
    surface_m2 = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("etablissement", "code")]
        ordering = ["batiment", "nom"]

    def __str__(self):
        return f"{self.nom} ({self.batiment})"
