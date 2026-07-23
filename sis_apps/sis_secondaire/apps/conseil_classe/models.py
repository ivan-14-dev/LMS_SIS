"""Models for conseil de classe (SIS Secondaire)."""
from django.db import models
from apps.classes.models import Classe
from apps.eleves.models import Eleve
from apps.etablissement.models import Periode
from apps.utilisateurs.models import Utilisateur


class ConseilClasse(models.Model):
    """Conseil de classe pour une classe et une période."""
    STATUT_CHOICES = [
        ("planifie", "Planifié"),
        ("tenu", "Tenu"),
        ("valide", "Validé"),
        ("annule", "Annulé"),
    ]
    classe = models.ForeignKey(Classe, on_delete=models.CASCADE, related_name="conseils")
    periode = models.ForeignKey(Periode, on_delete=models.CASCADE, related_name="conseils")
    date = models.DateTimeField()
    president = models.ForeignKey(
        Utilisateur, on_delete=models.PROTECT, related_name="conseils_presides"
    )
    secretaire = models.ForeignKey(
        Utilisateur, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="conseils_secretaires",
    )
    participants = models.ManyToManyField(
        Utilisateur, related_name="conseils_participes", blank=True
    )
    ordre_jour = models.TextField(blank=True)
    pv = models.TextField(blank=True)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default="planifie")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("classe", "periode")]
        ordering = ["-date"]
        verbose_name = "Conseil de classe"
        verbose_name_plural = "Conseils de classe"

    def __str__(self):
        return f"Conseil {self.classe} - {self.periode}"


class DecisionConseil(models.Model):
    """Décision du conseil pour un élève."""
    DECISION_CHOICES = [
        ("passage", "Passage en classe supérieure"),
        ("passage_conditionnel", "Passage conditionnel"),
        ("redoublement", "Redoublement"),
        ("orientation", "Réorientation"),
        ("encouragement", "Encouragements"),
        ("tableau_honneur", "Tableau d'honneur"),
        ("avertissement_travail", "Avertissement travail"),
        ("avertissement_comportement", "Avertissement comportement"),
        ("blame", "Blâme"),
    ]
    conseil = models.ForeignKey(ConseilClasse, on_delete=models.CASCADE, related_name="decisions")
    eleve = models.ForeignKey(Eleve, on_delete=models.CASCADE, related_name="decisions_conseil")
    decision = models.CharField(max_length=30, choices=DECISION_CHOICES)
    moyenne_generale = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    rang = models.PositiveIntegerField(null=True, blank=True)
    motif = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("conseil", "eleve")]
        verbose_name = "Décision de conseil"
        verbose_name_plural = "Décisions de conseil"

    def __str__(self):
        return f"{self.eleve} : {self.get_decision_display()}"


class AppreciationConseil(models.Model):
    """Appréciation générale du conseil pour un élève."""
    conseil = models.ForeignKey(ConseilClasse, on_delete=models.CASCADE, related_name="appreciations")
    eleve = models.ForeignKey(Eleve, on_delete=models.CASCADE, related_name="appreciations_conseil")
    appreciation = models.TextField()
    projet_orientation = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("conseil", "eleve")]

    def __str__(self):
        return f"Appréciation {self.eleve} - {self.conseil}"
