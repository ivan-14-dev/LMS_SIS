"""Models for enseignants (SIS Supérieur)."""
from django.db import models
from apps.structure.models import Faculte, Departement, Laboratoire
from apps.utilisateurs.models import Utilisateur
from apps.ue_ecue.models import ECUE, UE


class EnseignantChercheur(models.Model):
    """Enseignant-chercheur (MCF, PR, etc.)"""
    CORPS_CHOICES = [
        ("PR", "Professeur des universités"),
        ("MCF", "Maître de conférences"),
        ("PRAG", "PRAG"),
        ("PRCE", "PRCE"),
        ("ATER", "ATER"),
        ("Doctorant", "Doctorant contractuel"),
        ("Vacataire", "Vacataire"),
        ("Associé", "Professeur associé"),
        ("Invite", "Professeur invité"),
    ]
    user = models.OneToOneField(Utilisateur, on_delete=models.CASCADE, related_name="enseignant_profile")
    numero_harpe = models.CharField(max_length=20, blank=True, help_text="ID HARPEGE")
    corps = models.CharField(max_length=30, choices=CORPS_CHOICES, default="MCF")
    specialite = models.CharField(max_length=200)
    laboratoire = models.ForeignKey(
        Laboratoire, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="chercheurs"
    )
    h_index = models.PositiveSmallIntegerField(default=0)
    orcid = models.CharField(max_length=20, blank=True, help_text="0000-0000-0000-0000")
    id_hal = models.CharField(max_length=20, blank=True)
    id_ref = models.CharField(max_length=20, blank=True)
    bibliographie = models.JSONField(default=list, blank=True)
    annee_these = models.PositiveSmallIntegerField(null=True, blank=True)
    directeur_these = models.CharField(max_length=200, blank=True)
    rib_iban = models.CharField(max_length=50, blank=True)
    heures_service = models.DecimalField(max_digits=5, decimal_places=2, default=192)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Enseignant-chercheur"
        verbose_name_plural = "Enseignants-chercheurs"

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.get_corps_display()})"


class AffectationEnseignement(models.Model):
    """Affectation d'un enseignant à un ECUE/UE pour une année."""
    enseignant = models.ForeignKey(
        EnseignantChercheur, on_delete=models.CASCADE, related_name="affectations"
    )
    ue = models.ForeignKey(UE, on_delete=models.CASCADE, related_name="affectations", null=True, blank=True)
    ecue = models.ForeignKey(ECUE, on_delete=models.CASCADE, related_name="affectations", null=True, blank=True)
    type_enseignement = models.CharField(
        max_length=10,
        choices=[("CM", "Cours magistral"), ("TD", "TD"), ("TP", "TP")],
    )
    heures = models.DecimalField(max_digits=5, decimal_places=2)
    annee_universitaire = models.ForeignKey(
        "etablissement.AnneeUniversitaire", on_delete=models.CASCADE, related_name="affectations_enseignant"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Affectation enseignement"
        verbose_name_plural = "Affectations enseignements"

    def __str__(self):
        cible = self.ecue or self.ue
        return f"{self.enseignant} - {cible} ({self.type_enseignement})"
