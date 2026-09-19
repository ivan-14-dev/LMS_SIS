"""Models for releves (SIS Supérieur)."""

from apps.etablissement.models import AnneeUniversitaire, Semestre
from apps.etudiants.models import Etudiant
from apps.utilisateurs.models import Utilisateur
from django.db import models


class ReleveNotes(models.Model):
    """Relevé de notes semestriel."""

    etudiant = models.ForeignKey(
        Etudiant, on_delete=models.CASCADE, related_name="releves"
    )
    semestre = models.ForeignKey(
        Semestre, on_delete=models.PROTECT, related_name="releves"
    )
    pdf_path = models.CharField(max_length=500)
    moyenne_generale = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    mention = models.CharField(max_length=30, blank=True)
    credits_total = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    credits_valides = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    classement = models.PositiveIntegerField(null=True, blank=True)
    effectif = models.PositiveIntegerField(null=True, blank=True)
    date_emission = models.DateField()
    signe = models.BooleanField(default=False)
    date_signature = models.DateTimeField(null=True, blank=True)
    signe_par = models.ForeignKey(
        Utilisateur,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="releves_signes",
    )
    numero_serie = models.CharField(max_length=50, unique=True)
    qr_verification = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("etudiant", "semestre")]
        ordering = ["-semestre__date_fin"]
        verbose_name = "Relevé de notes"
        verbose_name_plural = "Relevés de notes"

    def __str__(self):
        return f"Relevé {self.etudiant} - {self.semestre}"


class Transcript(models.Model):
    """Transcript officiel (relevé global pluriannuel)."""

    etudiant = models.ForeignKey(
        Etudiant, on_delete=models.CASCADE, related_name="transcripts"
    )
    annees = models.ManyToManyField(AnneeUniversitaire, related_name="transcripts")
    pdf_path = models.CharField(max_length=500)
    credits_total = models.DecimalField(max_digits=5, decimal_places=2)
    credits_valides = models.DecimalField(max_digits=5, decimal_places=2)
    moyenne_ponderee = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    mention_finale = models.CharField(max_length=30, blank=True)
    diplome_prepare = models.CharField(max_length=200, blank=True)
    date_emission = models.DateField()
    numero_serie = models.CharField(max_length=50, unique=True)
    signe_par = models.ForeignKey(
        Utilisateur,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transcripts_signes",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Transcript"
        verbose_name_plural = "Transcripts"

    def __str__(self):
        return f"Transcript {self.etudiant} - {self.date_emission}"


class Attestation(models.Model):
    """Attestations diverses (réussite, inscription, comparabilité)."""

    TYPE_CHOICES = [
        ("reussite", "Attestation de réussite"),
        ("inscription", "Attestation d'inscription"),
        ("comparabilite", "Attestation de comparabilité"),
        ("relevé_notes", "Demande de relevé"),
        ("diplome", "Attestation de diplôme"),
        ("stage", "Attestation de stage"),
        ("mobilite", "Attestation de mobilité"),
    ]
    etudiant = models.ForeignKey(
        Etudiant, on_delete=models.CASCADE, related_name="attestations"
    )
    type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    pdf_path = models.CharField(max_length=500)
    date_emission = models.DateField()
    date_validite = models.DateField(null=True, blank=True)
    numero = models.CharField(max_length=50, unique=True)
    signe_par = models.ForeignKey(
        Utilisateur,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attestations_signees",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Attestation"
        verbose_name_plural = "Attestations"

    def __str__(self):
        return f"{self.get_type_display()} - {self.etudiant}"
