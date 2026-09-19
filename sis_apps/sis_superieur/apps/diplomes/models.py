"""Models for diplômes (SIS Supérieur)."""

from apps.etablissement.models import AnneeUniversitaire
from apps.etudiants.models import Etudiant
from apps.formations.models import Formation
from apps.utilisateurs.models import Utilisateur
from django.db import models


class Diplome(models.Model):
    """Type de diplôme (Licence, Master, etc.)."""

    TYPE_CHOICES = [
        ("national", "Diplôme national"),
        ("universite", "Diplôme d'université"),
        ("propre", "Diplôme propre"),
        ("co_diplome", "Co-diplôme"),
        ("etablissement", "Diplôme d'établissement"),
    ]
    formation = models.ForeignKey(
        Formation, on_delete=models.CASCADE, related_name="diplomes_type"
    )
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="national")
    nom = models.CharField(max_length=200)
    niveau_grade = models.CharField(
        max_length=50, help_text="Ex: Licence, Master, Doctorat"
    )
    code_rncp = models.CharField(
        max_length=20, blank=True, help_text="Code RNCP France"
    )
    credits_ects = models.PositiveSmallIntegerField(default=180)
    conditions = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Diplôme"
        verbose_name_plural = "Diplômes"

    def __str__(self):
        return self.nom


class CessionDiplome(models.Model):
    """Délivrance d'un diplôme à un étudiant."""

    etudiant = models.ForeignKey(
        Etudiant, on_delete=models.CASCADE, related_name="diplomes_obtenus"
    )
    diplome = models.ForeignKey(
        Diplome, on_delete=models.PROTECT, related_name="cessions"
    )
    annee_universitaire = models.ForeignKey(
        AnneeUniversitaire, on_delete=models.PROTECT, related_name="cessions_diplomes"
    )
    date_obtention = models.DateField()
    mention = models.CharField(max_length=30, blank=True)
    moyenne_finale = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    numero_serie = models.CharField(max_length=50, unique=True)
    pdf_path = models.CharField(max_length=500)
    signe_par = models.ForeignKey(
        Utilisateur,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="diplomes_signes",
    )
    date_signature = models.DateTimeField(null=True, blank=True)
    qr_verification = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("etudiant", "diplome", "annee_universitaire")]
        verbose_name = "Cession de diplôme"
        verbose_name_plural = "Cessions de diplôme"

    def __str__(self):
        return f"{self.etudiant} - {self.diplome} ({self.mention})"
