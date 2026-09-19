"""Models for emplois_du_temps (SIS Secondaire)."""

from apps.classes.models import Classe, Matiere
from apps.enseignants.models import Personnel
from apps.salles.models import Salle
from django.db import models


class Creneau(models.Model):
    """Créneau d'emploi du temps."""

    JOUR_CHOICES = [
        (1, "Lundi"),
        (2, "Mardi"),
        (3, "Mercredi"),
        (4, "Jeudi"),
        (5, "Vendredi"),
        (6, "Samedi"),
        (7, "Dimanche"),
    ]
    TYPE_CHOICES = [
        ("cours", "Cours"),
        ("td", "TD"),
        ("tp", "TP"),
        ("evaluation", "Évaluation"),
        ("permanence", "Permanence"),
        ("reunion", "Réunion"),
    ]
    classe = models.ForeignKey(
        Classe, on_delete=models.CASCADE, related_name="creneaux"
    )
    matiere = models.ForeignKey(
        Matiere, on_delete=models.PROTECT, related_name="creneaux"
    )
    enseignant = models.ForeignKey(
        Personnel, on_delete=models.PROTECT, related_name="creneaux"
    )
    salle = models.ForeignKey(
        Salle, on_delete=models.SET_NULL, null=True, blank=True, related_name="creneaux"
    )
    jour = models.PositiveSmallIntegerField(choices=JOUR_CHOICES)
    heure_debut = models.TimeField()
    heure_fin = models.TimeField()
    semaine = models.PositiveSmallIntegerField(
        default=0, help_text="0 = toutes les semaines"
    )
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="cours")
    date_specifique = models.DateField(
        null=True, blank=True, help_text="Si défini, créneau ponctuel"
    )
    notes = models.TextField(blank=True)
    actif = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["jour", "heure_debut"]
        indexes = [
            models.Index(fields=["classe", "jour"]),
            models.Index(fields=["enseignant", "jour"]),
            models.Index(fields=["salle", "jour"]),
        ]

    def __str__(self):
        return f"{self.get_jour_display()} {self.heure_debut} - {self.classe}/{self.matiere}"


class Contrainte(models.Model):
    """Contrainte pour la génération d'EDT."""

    TYPE_CHOICES = [
        ("indispo_enseignant", "Indisponibilité enseignant"),
        ("indispo_salle", "Indisponibilité salle"),
        ("indispo_classe", "Indisponibilité classe"),
        ("preference", "Préférence"),
    ]
    type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    enseignant = models.ForeignKey(
        Personnel,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="contraintes",
    )
    salle = models.ForeignKey(
        Salle,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="contraintes",
    )
    classe = models.ForeignKey(
        Classe,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="contraintes",
    )
    jour = models.PositiveSmallIntegerField(null=True, blank=True)
    heure_debut = models.TimeField(null=True, blank=True)
    heure_fin = models.TimeField(null=True, blank=True)
    priorite = models.PositiveSmallIntegerField(default=1)
    motif = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Contrainte"
        verbose_name_plural = "Contraintes"

    def __str__(self):
        return f"{self.get_type_display()} - priorité {self.priorite}"
