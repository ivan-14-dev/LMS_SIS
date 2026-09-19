"""Models for memoires (SIS Supérieur)."""
from django.db import models
from apps.formations.models import Formation
from apps.etudiants.models import Etudiant
from apps.enseignants.models import EnseignantChercheur
from apps.utilisateurs.models import Utilisateur


class SujetMemoire(models.Model):
    """Sujet de mémoire proposé par un enseignant."""
    STATUT_CHOICES = [
        ("propose", "Proposé"),
        ("attribue", "Attribué"),
        ("en_cours", "En cours"),
        ("soutenu", "Soutenu"),
        ("annule", "Annulé"),
    ]
    formation = models.ForeignKey(Formation, on_delete=models.CASCADE, related_name="sujets_memoire")
    annee_universitaire = models.ForeignKey(
        "etablissement.AnneeUniversitaire", on_delete=models.CASCADE, related_name="sujets_memoire"
    )
    titre = models.CharField(max_length=300)
    description = models.TextField()
    mots_cles = models.JSONField(default=list, blank=True)
    encadreur = models.ForeignKey(
        EnseignantChercheur, on_delete=models.PROTECT, related_name="memoires_encadres"
    )
    co_encadreur = models.ForeignKey(
        EnseignantChercheur, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="memoires_co_encadres",
    )
    laboratoire = models.ForeignKey(
        "recherche.Laboratoire", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="sujets_memoire",
    )
    nb_etudiants_max = models.PositiveSmallIntegerField(default=1)
    prerequis = models.TextField(blank=True)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default="propose")
    date_publication = models.DateField(null=True, blank=True)
    date_limite_candidature = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Sujet de mémoire"
        verbose_name_plural = "Sujets de mémoire"
        ordering = ["-created_at"]

    def __str__(self):
        return self.titre


class Memoire(models.Model):
    """Mémoire d'un étudiant."""
    STATUT_CHOICES = [
        ("brouillon", "Brouillon"),
        ("soumis", "Soumis"),
        ("en_relecture", "En relecture"),
        ("accepte", "Accepté"),
        ("reserve", "Sous réserve"),
        ("refuse", "Refusé"),
        ("soutenu", "Soutenu"),
    ]
    sujet = models.ForeignKey(SujetMemoire, on_delete=models.CASCADE, related_name="memoires")
    etudiant = models.OneToOneField(Etudiant, on_delete=models.CASCADE, related_name="memoire")
    fichier = models.FileField(upload_to="memoires/", null=True, blank=True)
    resume = models.TextField(blank=True)
    abstract = models.TextField(blank=True, help_text="Abstract en anglais")
    date_depot = models.DateTimeField(null=True, blank=True)
    rapport_similarite = models.FloatField(null=True, blank=True, help_text="% plagiat")
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default="brouillon")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Mémoire"
        verbose_name_plural = "Mémoires"

    def __str__(self):
        return f"Mémoire {self.etudiant} - {self.sujet.titre[:50]}"


class JuryMemoire(models.Model):
    """Jury de soutenance."""
    memoire = models.OneToOneField(Memoire, on_delete=models.CASCADE, related_name="jury")
    president = models.ForeignKey(
        Utilisateur, on_delete=models.PROTECT, related_name="jurys_memoire_presides"
    )
    rapporteurs = models.ManyToManyField(
        Utilisateur, related_name="rapports_memoire"
    )
    autres_membres = models.ManyToManyField(
        Utilisateur, blank=True, related_name="jurys_memoire_autres"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Jury mémoire {self.memoire}"


class SoutenanceMemoire(models.Model):
    """Soutenance d'un mémoire."""
    STATUT_CHOICES = [
        ("planifiee", "Planifiée"),
        ("reporte", "Reportée"),
        ("tenue", "Tenue"),
        ("annulee", "Annulée"),
    ]
    DECISION_CHOICES = [
        ("accepte", "Accepté"),
        ("accepte_reserve", "Accepté sous réserve"),
        ("refuse", "Refusé"),
    ]
    jury = models.OneToOneField(JuryMemoire, on_delete=models.CASCADE, related_name="soutenance")
    date = models.DateTimeField()
    duree_minutes = models.PositiveIntegerField(default=60)
    lieu = models.CharField(max_length=200)
    public = models.BooleanField(default=True)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default="planifiee")
    decision = models.CharField(max_length=30, choices=DECISION_CHOICES, blank=True)
    mention = models.CharField(max_length=30, blank=True)
    pv_pdf = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Soutenance"
        verbose_name_plural = "Soutenances"

    def __str__(self):
        return f"Soutenance {self.jury.memoire} - {self.date}"
