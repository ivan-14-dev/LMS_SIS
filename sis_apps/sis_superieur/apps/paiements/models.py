"""Models for paiements (SIS Supérieur)."""

from apps.etablissement.models import AnneeUniversitaire
from apps.etudiants.models import Etudiant
from apps.utilisateurs.models import Utilisateur
from django.db import models
from sis_common.exam_files import (
    PrivateFinancialStorage,
    payment_proof_upload_to,
    validate_payment_proof,
)


class TypeFraisInscription(models.Model):
    """Type de frais d'inscription (scolarité, CVEC, etc.)."""

    PERIODE_CHOICES = [
        ("unique", "Unique"),
        ("semestriel", "Semestriel"),
        ("annuel", "Annuel"),
    ]
    annee_universitaire = models.ForeignKey(AnneeUniversitaire, on_delete=models.CASCADE, related_name="types_frais")
    code = models.CharField(max_length=50)
    libelle = models.CharField(max_length=200)
    montant = models.DecimalField(max_digits=10, decimal_places=2)
    periodicite = models.CharField(max_length=20, choices=PERIODE_CHOICES, default="annuel")
    obligatoire = models.BooleanField(default=True)
    formations = models.ManyToManyField("formations.Formation", blank=True, related_name="types_frais")
    date_limite = models.DateField(null=True, blank=True)
    actif = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("annee_universitaire", "code")]
        verbose_name = "Type de frais d'inscription"
        verbose_name_plural = "Types de frais d'inscription"

    def __str__(self):
        return f"{self.libelle} ({self.montant}€)"


class FactureFrais(models.Model):
    """Facture de frais d'inscription."""

    STATUT_CHOICES = [
        ("brouillon", "Brouillon"),
        ("emise", "Émise"),
        ("payee", "Payée"),
        ("partielle", "Partiellement payée"),
        ("en_retard", "En retard"),
        ("annulee", "Annulée"),
    ]
    etudiant = models.ForeignKey(Etudiant, on_delete=models.PROTECT, related_name="factures")
    type_frais = models.ForeignKey(TypeFraisInscription, on_delete=models.PROTECT, related_name="factures")
    numero = models.CharField(max_length=50, unique=True)
    date_emission = models.DateField()
    date_echeance = models.DateField()
    montant = models.DecimalField(max_digits=10, decimal_places=2)
    montant_paye = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default="emise")
    note = models.TextField(blank=True)
    pdf_path = models.CharField(max_length=500, blank=True)
    qr_paiement = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date_emission"]
        indexes = [
            models.Index(fields=["etudiant", "statut"]),
        ]

    def __str__(self):
        return f"Facture {self.numero} - {self.etudiant}"


class PaiementFrais(models.Model):
    """Paiement d'une facture."""

    MODE_CHOICES = [
        ("especes", "Espèces"),
        ("cheque", "Chèque"),
        ("virement", "Virement"),
        ("carte", "Carte bancaire"),
        ("mobile_money", "Mobile Money"),
        ("sepa", "Prélèvement SEPA"),
    ]
    STATUT_CHOICES = [
        ("en_attente", "En attente"),
        ("valide", "Validé"),
        ("echec", "Échec"),
        ("rejete", "Rejeté"),
        ("rembourse", "Remboursé"),
    ]
    facture = models.ForeignKey(FactureFrais, on_delete=models.CASCADE, related_name="paiements")
    numero = models.CharField(max_length=50, unique=True)
    date_paiement = models.DateField()
    montant = models.DecimalField(max_digits=10, decimal_places=2)
    mode = models.CharField(max_length=20, choices=MODE_CHOICES)
    reference_externe = models.CharField(max_length=200, blank=True)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default="valide")
    recu_pdf = models.CharField(max_length=500, blank=True)
    preuve_paiement = models.FileField(
        upload_to=payment_proof_upload_to,
        storage=PrivateFinancialStorage(),
        validators=[validate_payment_proof],
        null=True,
        blank=True,
    )
    enregistre_par = models.ForeignKey(
        Utilisateur,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="paiements_enregistres",
    )
    verifie_par = models.ForeignKey(
        Utilisateur,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="paiements_verifies",
    )
    verifie_le = models.DateTimeField(null=True, blank=True)
    motif_rejet = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_paiement"]

    def __str__(self):
        return f"Paiement {self.numero} - {self.montant}€"


class Bourse(models.Model):
    """Bourse et aide financière."""

    TYPE_CHOICES = [
        ("sociale", "Bourse sur critères sociaux"),
        ("merite", "Bourse au mérite"),
        ("mobilite", "Bourse de mobilité"),
        ("these", "Bourse de thèse"),
        ("urgence", "Aide d'urgence"),
        ("exoneration", "Exonération"),
    ]
    etudiant = models.ForeignKey(Etudiant, on_delete=models.CASCADE, related_name="bourses")
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    montant_total = models.DecimalField(max_digits=10, decimal_places=2)
    montant_verse = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    date_debut = models.DateField()
    date_fin = models.DateField()
    numero_dossier = models.CharField(max_length=50, unique=True)
    conditions = models.TextField(blank=True)
    statut = models.CharField(
        max_length=20,
        choices=[
            ("en_attente", "En attente"),
            ("accordee", "Accordée"),
            ("refusee", "Refusée"),
            ("suspendue", "Suspendue"),
        ],
        default="en_attente",
    )
    motif_refus = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Bourse"
        verbose_name_plural = "Bourses"

    def __str__(self):
        return f"{self.get_type_display()} - {self.etudiant}"


class VersementBourse(models.Model):
    """Versement d'une bourse."""

    bourse = models.ForeignKey(Bourse, on_delete=models.CASCADE, related_name="versements")
    date_versement = models.DateField()
    montant = models.DecimalField(max_digits=10, decimal_places=2)
    mode = models.CharField(max_length=20, default="virement")
    reference = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_versement"]
        verbose_name = "Versement de bourse"
        verbose_name_plural = "Versements de bourse"

    def __str__(self):
        return f"{self.bourse} - {self.montant}€"
