"""Models for bourses (SIS Supérieur)."""
from django.db import models
from apps.etudiants.models import Etudiant
from apps.etablissement.models import AnneeUniversitaire
from apps.utilisateurs.models import Utilisateur


class TypeBourse(models.Model):
    """Type de bourse disponible."""
    CATEGORIE_CHOICES = [
        ("merite", "Bourse au mérite"),
        ("sociale", "Bourse sociale"),
        ("excellence", "Bourse d'excellence"),
        ("mobilite", "Bourse de mobilité"),
        ("recherche", "Bourse de recherche"),
        ("stage", "Bourse de stage"),
        ("handicap", "Aide handicap"),
        ("urgence", "Aide d'urgence"),
    ]
    nom = models.CharField(max_length=200)
    categorie = models.CharField(max_length=20, choices=CATEGORIE_CHOICES)
    description = models.TextField(blank=True)
    montant_mensuel = models.DecimalField(max_digits=10, decimal_places=2)
    duree_mois = models.PositiveSmallIntegerField(default=10, help_text="Durée en mois")
    criteres_eligibilite = models.TextField(blank=True, help_text="Critères détaillés")
    moyenne_minimale = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text="Moyenne minimale requise"
    )
    plafond_ressources = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text="Plafond de ressources familiales"
    )
    pieces_requises = models.JSONField(default=list, blank=True)
    quota_annuel = models.PositiveIntegerField(null=True, blank=True)
    actif = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Type de bourse"
        verbose_name_plural = "Types de bourses"
        ordering = ['categorie', 'nom']

    def __str__(self):
        return f"{self.nom} ({self.get_categorie_display()})"


class DemandeBourse(models.Model):
    """Demande de bourse par un étudiant."""
    STATUT_CHOICES = [
        ("brouillon", "Brouillon"),
        ("soumise", "Soumise"),
        ("en_instruction", "En instruction"),
        ("complete", "Dossier complet"),
        ("incomplete", "Dossier incomplet"),
        ("acceptee", "Acceptée"),
        ("refusee", "Refusée"),
        ("liste_attente", "Liste d'attente"),
        ("annulee", "Annulée"),
    ]
    etudiant = models.ForeignKey(
        Etudiant, on_delete=models.CASCADE, related_name="demandes_bourses"
    )
    type_bourse = models.ForeignKey(
        TypeBourse, on_delete=models.PROTECT, related_name="demandes"
    )
    annee_universitaire = models.ForeignKey(
        AnneeUniversitaire, on_delete=models.PROTECT, related_name="demandes_bourses"
    )
    lettre_motivation = models.TextField(blank=True)
    justificatifs = models.JSONField(default=list, blank=True, help_text="Liste des fichiers")
    revenus_declares = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    moyenne_actuelle = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default="brouillon")
    date_soumission = models.DateTimeField(null=True, blank=True)
    date_decision = models.DateTimeField(null=True, blank=True)
    decision_par = models.ForeignKey(
        Utilisateur, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="decisions_bourses"
    )
    motif_refus = models.TextField(blank=True)
    commentaires_instruction = models.TextField(blank=True)
    rang_liste_attente = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Demande de bourse"
        verbose_name_plural = "Demandes de bourses"
        unique_together = [("etudiant", "type_bourse", "annee_universitaire")]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.etudiant} - {self.type_bourse.nom} ({self.annee_universitaire})"


class AttributionBourse(models.Model):
    """Attribution et versements d'une bourse."""
    STATUT_CHOICES = [
        ("active", "Active"),
        ("suspendue", "Suspendue"),
        ("terminee", "Terminée"),
        ("annulee", "Annulée"),
    ]
    demande = models.OneToOneField(
        DemandeBourse, on_delete=models.CASCADE, related_name="attribution"
    )
    numero_attribution = models.CharField(max_length=50, unique=True)
    date_debut = models.DateField()
    date_fin = models.DateField()
    montant_mensuel = models.DecimalField(max_digits=10, decimal_places=2)
    montant_total = models.DecimalField(max_digits=12, decimal_places=2)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default="active")
    rib_iban = models.CharField(max_length=34, blank=True)
    titulaire_compte = models.CharField(max_length=200, blank=True)
    motif_suspension = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Attribution de bourse"
        verbose_name_plural = "Attributions de bourses"

    def __str__(self):
        return f"{self.numero_attribution} - {self.demande.etudiant}"


class VersementBourse(models.Model):
    """Versement individuel d'une bourse."""
    STATUT_CHOICES = [
        ("planifie", "Planifié"),
        ("en_cours", "En cours"),
        ("effectue", "Effectué"),
        ("rejete", "Rejeté"),
        ("annule", "Annulé"),
    ]
    attribution = models.ForeignKey(
        AttributionBourse, on_delete=models.CASCADE, related_name="versements"
    )
    mois = models.DateField(help_text="Premier jour du mois concerné")
    montant = models.DecimalField(max_digits=10, decimal_places=2)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default="planifie")
    date_virement = models.DateField(null=True, blank=True)
    reference_virement = models.CharField(max_length=100, blank=True)
    commentaire = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Versement de bourse"
        verbose_name_plural = "Versements de bourses"
        unique_together = [("attribution", "mois")]
        ordering = ['mois']

    def __str__(self):
        return f"{self.attribution.numero_attribution} - {self.mois.strftime('%m/%Y')}"
