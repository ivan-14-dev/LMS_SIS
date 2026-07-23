"""Models for cantine (SIS Secondaire)."""
from django.db import models
from apps.eleves.models import Eleve


class Menu(models.Model):
    """Menu de la cantine pour un jour."""
    date = models.DateField()
    entree = models.CharField(max_length=200, blank=True)
    plat = models.CharField(max_length=200)
    accompagnement = models.CharField(max_length=200, blank=True)
    dessert = models.CharField(max_length=200, blank=True)
    regime = models.CharField(
        max_length=20,
        choices=[("standard", "Standard"), ("vegetarien", "Végétarien"), ("sans_porc", "Sans porc"), ("sans_gluten", "Sans gluten"), ("autre", "Autre")],
        default="standard",
    )
    prix = models.DecimalField(max_digits=6, decimal_places=2, default=0)

    class Meta:
        unique_together = [("date", "regime")]
        verbose_name = "Menu"
        verbose_name_plural = "Menus"
        ordering = ["date"]

    def __str__(self):
        return f"Menu {self.date} - {self.plat}"


class InscriptionCantine(models.Model):
    """Inscription d'un élève à la cantine."""
    FORFAIT_CHOICES = [
        ("annuel", "Annuel"),
        ("trimestriel", "Trimestriel"),
        ("mensuel", "Mensuel"),
        ("unitaire", "Unitaire"),
    ]
    eleve = models.OneToOneField(Eleve, on_delete=models.CASCADE, related_name="inscription_cantine")
    forfait = models.CharField(max_length=20, choices=FORFAIT_CHOICES, default="annuel")
    date_debut = models.DateField()
    date_fin = models.DateField(null=True, blank=True)
    regime = models.CharField(
        max_length=20,
        choices=[("standard", "Standard"), ("vegetarien", "Végétarien"), ("sans_porc", "Sans porc"), ("sans_gluten", "Sans gluten")],
        default="standard",
    )
    allergies = models.JSONField(default=list, blank=True)
    actif = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Inscription cantine"
        verbose_name_plural = "Inscriptions cantine"

    def __str__(self):
        return f"Cantine {self.eleve}"


class PresenceCantine(models.Model):
    """Présence effective à la cantine (pointage)."""
    menu = models.ForeignKey(Menu, on_delete=models.CASCADE, related_name="presences")
    eleve = models.ForeignKey(Eleve, on_delete=models.CASCADE, related_name="presences_cantine")
    present = models.BooleanField(default=True)
    heure_pointage = models.TimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("menu", "eleve")]
        verbose_name = "Présence cantine"
        verbose_name_plural = "Présences cantine"

    def __str__(self):
        return f"{self.eleve} - {self.menu.date}"
