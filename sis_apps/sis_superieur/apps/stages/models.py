"""Models for stages (SIS Supérieur)."""
from django.db import models
from apps.etudiants.models import Etudiant
from apps.entreprises.models import Entreprise
from apps.utilisateurs.models import Utilisateur
from apps.enseignants.models import EnseignantChercheur
from apps.formations.models import Formation


class OffreStage(models.Model):
    """Offre de stage."""
    TYPE_CHOICES = [
        ("observation", "Stage d'observation (L1)"),
        ("application", "Stage d'application (L2-L3)"),
        ("fin_etudes", "Stage de fin d'études (M1/M2)"),
        ("alternance", "Alternance"),
        ("recherche", "Stage de recherche"),
    ]
    STATUT_CHOICES = [
        ("ouverte", "Ouverte"),
        ("fermee", "Fermée"),
        ("pourvue", "Pourvue"),
        ("annulee", "Annulée"),
    ]
    formation = models.ForeignKey(
        Formation, on_delete=models.CASCADE, related_name="offres_stage",
        null=True, blank=True,
    )
    entreprise = models.ForeignKey(Entreprise, on_delete=models.CASCADE, related_name="offres_stage")
    titre = models.CharField(max_length=200)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    description = models.TextField()
    missions = models.JSONField(default=list, blank=True)
    competences_requises = models.JSONField(default=list, blank=True)
    duree_mois = models.DecimalField(max_digits=4, decimal_places=1)
    date_debut = models.DateField()
    date_fin = models.DateField()
    remuneration = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    devise = models.CharField(max_length=3, default="EUR")
    nb_places = models.PositiveSmallIntegerField(default=1)
    lieu = models.CharField(max_length=200)
    pays = models.CharField(max_length=100, default="France")
    reference = models.CharField(max_length=50, blank=True)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default="ouverte")
    date_limite_candidature = models.DateField()
    publiee = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Offre de stage"
        verbose_name_plural = "Offres de stage"

    def __str__(self):
        return self.titre


class CandidatureStage(models.Model):
    """Candidature à une offre de stage."""
    STATUT_CHOICES = [
        ("soumise", "Soumise"),
        ("preselectionne", "Présélectionnée"),
        ("entretien", "Entretien planifié"),
        ("acceptee", "Acceptée"),
        ("refusee", "Refusée"),
        ("annulee", "Annulée"),
    ]
    etudiant = models.ForeignKey(Etudiant, on_delete=models.CASCADE, related_name="candidatures_stage")
    offre = models.ForeignKey(OffreStage, on_delete=models.CASCADE, related_name="candidatures")
    lettre_motivation = models.TextField()
    cv = models.FileField(upload_to="stages/cv/")
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default="soumise")
    date_soumission = models.DateTimeField(auto_now_add=True)
    date_reponse = models.DateTimeField(null=True, blank=True)
    motif_refus = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Candidature stage"
        verbose_name_plural = "Candidatures stage"

    def __str__(self):
        return f"{self.etudiant} - {self.offre}"


class ConventionStage(models.Model):
    """Convention de stage tripartite."""
    STATUT_CHOICES = [
        ("brouillon", "Brouillon"),
        ("signee_etudiant", "Signée par l'étudiant"),
        ("signee_entreprise", "Signée par l'entreprise"),
        ("signee_ecole", "Signée par l'école"),
        ("complete", "Complète"),
        ("annulee", "Annulée"),
    ]
    etudiant = models.ForeignKey(Etudiant, on_delete=models.CASCADE, related_name="conventions_stage")
    offre = models.OneToOneField(OffreStage, on_delete=models.PROTECT, related_name="convention")
    entreprise = models.ForeignKey(Entreprise, on_delete=models.PROTECT, related_name="conventions")
    maitre_stage = models.ForeignKey(
        "entreprises.ContactEntreprise", on_delete=models.PROTECT, related_name="stages_encadres"
    )
    tuteur_pedagogique = models.ForeignKey(
        EnseignantChercheur, on_delete=models.PROTECT, related_name="stages_tutelles"
    )
    date_debut = models.DateField()
    date_fin = models.DateField()
    gratification = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    horaires = models.CharField(max_length=200, blank=True)
    missions = models.TextField()
    pdf_path = models.CharField(max_length=500)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default="brouillon")
    date_signature_complete = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Convention de stage"
        verbose_name_plural = "Conventions de stage"

    def __str__(self):
        return f"{self.etudiant} - {self.entreprise}"


class SuiviStage(models.Model):
    """Suivi de stage par le tuteur pédagogique."""
    TYPE_CHOICES = [
        ("visite", "Visite sur site"),
        ("entretien_tel", "Entretien téléphonique"),
        ("point_ecrit", "Point écrit"),
        ("evaluation_mi_parcours", "Évaluation mi-parcours"),
    ]
    convention = models.ForeignKey(ConventionStage, on_delete=models.CASCADE, related_name="suivis")
    type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    date = models.DateField()
    commentaires = models.TextField()
    appreciation = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Suivi de stage"
        verbose_name_plural = "Suivis de stage"

    def __str__(self):
        return f"{self.convention} - {self.get_type_display()}"


class EvaluationTuteur(models.Model):
    """Évaluation finale par le tuteur entreprise."""
    convention = models.OneToOneField(ConventionStage, on_delete=models.CASCADE, related_name="evaluation_tuteur")
    note_globale = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    competences_techniques = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    competences_relationnelles = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    autonomie = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    commentaires = models.TextField(blank=True)
    date_evaluation = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Évaluation tuteur"
        verbose_name_plural = "Évaluations tuteurs"

    def __str__(self):
        return f"Évaluation {self.convention}"


class RapportStage(models.Model):
    """Rapport de stage rendu par l'étudiant."""
    STATUT_CHOICES = [
        ("brouillon", "Brouillon"),
        ("soumis", "Soumis"),
        ("accepte", "Accepté"),
        ("refuse", "Refusé"),
    ]
    convention = models.OneToOneField(ConventionStage, on_delete=models.CASCADE, related_name="rapport")
    fichier = models.FileField(upload_to="stages/rapports/")
    date_soumission = models.DateTimeField(null=True, blank=True)
    note_finale = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    appreciation = models.TextField(blank=True)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default="brouillon")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Rapport de stage"
        verbose_name_plural = "Rapports de stage"

    def __str__(self):
        return f"Rapport {self.convention}"
