"""Models for jurys et délibérations (SIS Supérieur)."""
from django.db import models
from apps.formations.models import Formation, Parcours
from apps.etablissement.models import Semestre
from apps.utilisateurs.models import Utilisateur
from apps.ue_ecue.models import UE
from apps.etudiants.models import Etudiant


class Jury(models.Model):
    """Jury de délibération."""
    STATUT_CHOICES = [
        ("planifie", "Planifié"),
        ("convoque", "Convoqué"),
        ("reuni", "Réuni"),
        ("delibere", "Délibéré"),
        ("cloture", "Clôturé"),
        ("annule", "Annulé"),
    ]
    semestre = models.ForeignKey(Semestre, on_delete=models.CASCADE, related_name="jurys")
    formation = models.ForeignKey(Formation, on_delete=models.CASCADE, related_name="jurys")
    parcours = models.ForeignKey(
        Parcours, on_delete=models.CASCADE, null=True, blank=True, related_name="jurys"
    )
    date = models.DateTimeField()
    lieu = models.CharField(max_length=200)
    president = models.ForeignKey(
        Utilisateur, on_delete=models.PROTECT, related_name="jurys_presides"
    )
    secretaire = models.ForeignKey(
        Utilisateur, on_delete=models.PROTECT, related_name="jurys_secretaires"
    )
    membres = models.ManyToManyField(Utilisateur, related_name="jurys_membre")
    ordre_jour = models.TextField(blank=True)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default="planifie")
    pv_pdf = models.CharField(max_length=500, blank=True)
    date_pv = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"Jury {self.formation} - {self.semestre} - {self.date}"


class Deliberation(models.Model):
    """Délibération d'un jury."""
    jury = models.OneToOneField(Jury, on_delete=models.CASCADE, related_name="deliberation")
    date_ouverture = models.DateTimeField(auto_now_add=True)
    date_cloture = models.DateTimeField(null=True, blank=True)
    nb_admis = models.PositiveIntegerField(default=0)
    nb_ajournes = models.PositiveIntegerField(default=0)
    nb_refuses = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True, help_text="Notes de délibération")
    pv_pdf = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Délibération {self.jury}"


class DecisionJury(models.Model):
    """Décision du jury pour un étudiant / UE."""
    DECISION_CHOICES = [
        ("valide", "Validé"),
        ("compense", "Compensé"),
        ("ajourne", "Ajourné"),
        ("refuse", "Refusé"),
        ("reorientation", "Réorientation"),
        ("absence_examen", "Absence injustifiée"),
    ]
    deliberation = models.ForeignKey(
        Deliberation, on_delete=models.CASCADE, related_name="decisions"
    )
    etudiant = models.ForeignKey(Etudiant, on_delete=models.CASCADE, related_name="decisions_jury")
    ue = models.ForeignKey(UE, on_delete=models.CASCADE, related_name="decisions_jury")
    decision = models.CharField(max_length=20, choices=DECISION_CHOICES)
    note = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    commentaire = models.TextField(blank=True)
    voix_pour = models.PositiveSmallIntegerField(default=0)
    voix_contre = models.PositiveSmallIntegerField(default=0)
    abstentions = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("deliberation", "etudiant", "ue")]

    def __str__(self):
        return f"{self.etudiant} - {self.ue} : {self.get_decision_display()}"


class DecisionGlobale(models.Model):
    """Décision globale du jury pour un étudiant (admis, ajourné, refusé)."""
    DECISION_CHOICES = [
        ("admis", "Admis"),
        ("admis_mention", "Admis avec mention"),
        ("admis_sous_condition", "Admis sous condition"),
        ("ajourne", "Ajourné"),
        ("refuse", "Refusé"),
        ("reorientation", "Réorientation"),
        ("redoublement", "Redoublement"),
    ]
    deliberation = models.ForeignKey(
        Deliberation, on_delete=models.CASCADE, related_name="decisions_globales"
    )
    etudiant = models.ForeignKey(Etudiant, on_delete=models.CASCADE, related_name="decisions_globales")
    decision = models.CharField(max_length=30, choices=DECISION_CHOICES)
    moyenne_generale = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    mention = models.CharField(max_length=30, blank=True)
    commentaire = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("deliberation", "etudiant")]

    def __str__(self):
        return f"{self.etudiant} : {self.get_decision_display()}"
