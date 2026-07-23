"""Models for structure (Faculté / Département) (SIS Supérieur)."""
from django.db import models
from apps.etablissement.models import Universite
from apps.utilisateurs.models import Utilisateur


class Faculte(models.Model):
    """Faculté d'une université."""
    universite = models.ForeignKey(
        Universite, on_delete=models.CASCADE, related_name="facultes"
    )
    nom = models.CharField(max_length=200)
    code = models.CharField(max_length=20)
    doyen = models.ForeignKey(
        Utilisateur, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="facultes_dirigees",
        limit_choices_to={"role__in": ["doyen", "vice_president"]},
    )
    date_creation = models.DateField(null=True, blank=True)
    description = models.TextField(blank=True)
    actif = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("universite", "code")]
        verbose_name = "Faculté"
        verbose_name_plural = "Facultés"

    def __str__(self):
        return f"{self.code} - {self.nom}"


class Departement(models.Model):
    """Département d'une faculté."""
    faculte = models.ForeignKey(
        Faculte, on_delete=models.CASCADE, related_name="departements"
    )
    nom = models.CharField(max_length=200)
    code = models.CharField(max_length=20)
    directeur = models.ForeignKey(
        Utilisateur, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="departements_diriges",
        limit_choices_to={"role__in": ["directeur_dept", "doyen"]},
    )
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("faculte", "code")]
        verbose_name = "Département"
        verbose_name_plural = "Départements"

    def __str__(self):
        return f"{self.code} - {self.nom}"


class EcoleDoctorale(models.Model):
    """École doctorale."""
    universite = models.ForeignKey(
        Universite, on_delete=models.CASCADE, related_name="ecoles_doctorales"
    )
    nom = models.CharField(max_length=200)
    code = models.CharField(max_length=20)
    directeur = models.ForeignKey(
        Utilisateur, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="ecoles_dirigees",
    )
    domaines = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("universite", "code")]
        verbose_name = "École doctorale"
        verbose_name_plural = "Écoles doctorales"

    def __str__(self):
        return self.nom
