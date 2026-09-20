"""Models for UE et ECUE (SIS Supérieur)."""

from apps.etablissement.models import Semestre
from apps.formations.models import MaquetteFormation, Parcours
from django.db import models


class UE(models.Model):
    """Unité d'Enseignement."""

    TYPE_CHOICES = [
        ("F", "Fondamentale"),
        ("S", "Spécialité"),
        ("C", "Complémentaire"),
        ("O", "Optionnelle"),
        ("L", "Libre"),
    ]
    MH_GLOBAL_CHOICES = [
        ("mutable", "Mutable"),
        ("non_calculable", "Non calculable"),
        ("calculable_separement", "Calculable séparément"),
    ]
    maquette = models.ForeignKey(MaquetteFormation, on_delete=models.CASCADE, related_name="ues")
    code = models.CharField(max_length=30)
    nom = models.CharField(max_length=200)
    credits_ects = models.DecimalField(max_digits=4, decimal_places=2)
    type = models.CharField(max_length=100, default="F")
    volume_horaire_cm = models.PositiveIntegerField(default=0, help_text="Heures CM")
    volume_horaire_td = models.PositiveIntegerField(default=0, help_text="Heures TD")
    volume_horaire_tp = models.PositiveIntegerField(default=0, help_text="Heures TP")
    semestre = models.ForeignKey(Semestre, on_delete=models.PROTECT, related_name="ues")
    mh_global = models.CharField(max_length=30, choices=MH_GLOBAL_CHOICES, default="calculable_separement")
    parcours_autorises = models.ManyToManyField(Parcours, blank=True, related_name="ues")
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("maquette", "code")]
        verbose_name = "Unité d'Enseignement"
        verbose_name_plural = "Unités d'Enseignement"
        ordering = ["semestre", "code"]

    def __str__(self):
        return f"{self.code} - {self.nom}"

    def get_type_display(self):
        return dict(self.TYPE_CHOICES).get(self.type, self.type)

    @property
    def volume_horaire_total(self):
        return self.volume_horaire_cm + self.volume_horaire_td + self.volume_horaire_tp


class ECUE(models.Model):
    """Élément Constitutif d'UE."""

    ue = models.ForeignKey(UE, on_delete=models.CASCADE, related_name="ecues")
    code = models.CharField(max_length=30)
    nom = models.CharField(max_length=200)
    credits_ects = models.DecimalField(max_digits=4, decimal_places=2)
    volume_horaire_cm = models.PositiveIntegerField(default=0)
    volume_horaire_td = models.PositiveIntegerField(default=0)
    volume_horaire_tp = models.PositiveIntegerField(default=0)
    coefficient = models.DecimalField(max_digits=4, decimal_places=2, default=1)
    description = models.TextField(blank=True)
    programme = models.TextField(blank=True)
    bibliographie = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("ue", "code")]
        verbose_name = "ECUE"
        verbose_name_plural = "ECUEs"
        ordering = ["ue", "code"]

    def __str__(self):
        return f"{self.ue.code}.{self.code} - {self.nom}"


class Prerequis(models.Model):
    """UE prérequise pour s'inscrire à une autre."""

    TYPE_CHOICES = [
        ("capitalisee", "UE capitalisée"),
        ("moyenne_ue", "Moyenne UE"),
        ("note_minimale", "Note minimale"),
    ]
    ue_cible = models.ForeignKey(UE, on_delete=models.CASCADE, related_name="prerequis_requis")
    ue_prereq = models.ForeignKey(UE, on_delete=models.CASCADE, related_name="est_prerequis_de")
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="capitalisee")
    note_minimale = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Si type = note_minimale",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("ue_cible", "ue_prereq")]
        verbose_name = "Prérequis"
        verbose_name_plural = "Prérequis"

    def __str__(self):
        return f"{self.ue_cible} ← {self.ue_prereq}"


class Capitalisation(models.Model):
    """Règle de capitalisation."""

    type = models.CharField(max_length=20, default="note_seuil")
    note_seuil = models.DecimalField(max_digits=4, decimal_places=2, default=10)
    compensation_autorisee = models.BooleanField(default=True)
    note_seuil_compensation = models.DecimalField(max_digits=4, decimal_places=2, default=8)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Capitalisation"
        verbose_name_plural = "Capitalisations"

    def __str__(self):
        return f"{self.type} ({self.note_seuil})"
