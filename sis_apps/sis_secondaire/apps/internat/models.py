"""Models for internat (SIS Secondaire)."""

from apps.eleves.models import Eleve
from django.db import models


class BatimentInternat(models.Model):
    """Bâtiment d'internat."""

    nom = models.CharField(max_length=100)
    adresse = models.CharField(max_length=200, blank=True)
    nb_etages = models.PositiveSmallIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Bâtiment internat"
        verbose_name_plural = "Bâtiments internat"

    def __str__(self):
        return self.nom


class Chambre(models.Model):
    """Chambre d'internat."""

    TYPE_CHOICES = [
        ("simple", "Simple"),
        ("double", "Double"),
        ("triple", "Triple"),
        ("quadruple", "Quadruple"),
    ]
    batiment = models.ForeignKey(
        BatimentInternat, on_delete=models.CASCADE, related_name="chambres"
    )
    numero = models.CharField(max_length=20)
    etage = models.PositiveSmallIntegerField(default=0)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="double")
    capacite = models.PositiveSmallIntegerField(default=2)
    equipements = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("batiment", "numero")]
        verbose_name = "Chambre"
        verbose_name_plural = "Chambres"

    def __str__(self):
        return f"{self.batiment.nom} - Chambre {self.numero}"


class OccupantChambre(models.Model):
    """Occupation d'une chambre par un élève."""

    chambre = models.ForeignKey(
        Chambre, on_delete=models.CASCADE, related_name="occupants"
    )
    eleve = models.ForeignKey(
        Eleve, on_delete=models.CASCADE, related_name="chambres_occupations"
    )
    date_debut = models.DateField()
    date_fin = models.DateField(null=True, blank=True)
    motif_fin = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Occupant chambre"
        verbose_name_plural = "Occupants chambre"

    def __str__(self):
        return f"{self.eleve} - Chambre {self.chambre.numero}"


class EtudeSurveillee(models.Model):
    """Séance d'étude du soir."""

    batiment = models.ForeignKey(
        BatimentInternat, on_delete=models.CASCADE, related_name="etudes"
    )
    salle = models.CharField(max_length=100)
    date = models.DateField()
    heure_debut = models.TimeField()
    heure_fin = models.TimeField()
    surveillant = models.ForeignKey(
        "utilisateurs.Utilisateur", on_delete=models.PROTECT, related_name="etudes_surv"
    )
    eleves_presents = models.ManyToManyField(Eleve, related_name="etudes_presence")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Étude surveillée"
        verbose_name_plural = "Études surveillées"

    def __str__(self):
        return f"Étude {self.salle} - {self.date}"
