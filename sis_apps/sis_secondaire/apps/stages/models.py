"""Models for stages (filière pro - SIS Secondaire)."""
from django.db import models
from apps.eleves.models import Eleve
from apps.utilisateurs.models import Utilisateur


class Entreprise(models.Model):
    """Entreprise d'accueil pour les stages."""
    raison_sociale = models.CharField(max_length=200)
    siret = models.CharField(max_length=20, blank=True)
    secteur = models.CharField(max_length=100, blank=True)
    taille = models.CharField(max_length=20, blank=True)
    adresse = models.TextField()
    code_postal = models.CharField(max_length=10)
    ville = models.CharField(max_length=100)
    telephone = models.CharField(max_length=20)
    email = models.EmailField(blank=True)
    contact_nom = models.CharField(max_length=200, blank=True)
    contact_fonction = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Entreprise"
        verbose_name_plural = "Entreprises"
        ordering = ["raison_sociale"]

    def __str__(self):
        return self.raison_sociale


class ConventionStage(models.Model):
    """Convention de stage (filière pro)."""
    STATUT_CHOICES = [
        ("brouillon", "Brouillon"),
        ("signee_etudiant", "Signée élève"),
        ("signee_entreprise", "Signée entreprise"),
        ("signee_etablissement", "Signée établissement"),
        ("complete", "Complète"),
        ("annulee", "Annulée"),
    ]
    eleve = models.ForeignKey(Eleve, on_delete=models.CASCADE, related_name="conventions_stage")
    entreprise = models.ForeignKey(Entreprise, on_delete=models.PROTECT, related_name="conventions")
    tuteur_entreprise = models.CharField(max_length=200)
    telephone_tuteur = models.CharField(max_length=20)
    email_tuteur = models.EmailField()
    maitre_stage_etablissement = models.ForeignKey(
        Utilisateur, on_delete=models.PROTECT, related_name="stages_suivis"
    )
    date_debut = models.DateField()
    date_fin = models.DateField()
    duree_heures = models.PositiveIntegerField()
    remuneration = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    missions = models.TextField()
    horaires = models.CharField(max_length=200, blank=True)
    pdf_path = models.CharField(max_length=500)
    statut = models.CharField(max_length=30, choices=STATUT_CHOICES, default="brouillon")
    date_signature_complete = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Convention de stage"
        verbose_name_plural = "Conventions de stage"

    def __str__(self):
        return f"Stage {self.eleve} - {self.entreprise}"


class SuiviStage(models.Model):
    """Suivi de stage par le maître de stage."""
    TYPE_CHOICES = [
        ("visite", "Visite sur site"),
        ("appel", "Appel téléphonique"),
        ("rapport", "Rapport écrit"),
    ]
    convention = models.ForeignKey(ConventionStage, on_delete=models.CASCADE, related_name="suivis")
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    date = models.DateField()
    commentaires = models.TextField()
    appreciation = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Suivi de stage"
        verbose_name_plural = "Suivis de stage"

    def __str__(self):
        return f"{self.convention} - {self.get_type_display()}"


class EvaluationStage(models.Model):
    """Évaluation finale du stage."""
    convention = models.OneToOneField(ConventionStage, on_delete=models.CASCADE, related_name="evaluation")
    note_entreprise = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    note_etablissement = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    note_soutenance = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    note_finale = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    rapport = models.FileField(upload_to="stages/rapports/", null=True, blank=True)
    appreciation_globale = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Évaluation de stage"
        verbose_name_plural = "Évaluations de stage"

    def __str__(self):
        return f"Évaluation {self.convention}"
