"""Models for paiements (SIS Secondaire)."""

from apps.eleves.models import Eleve
from apps.etablissement.models import AnneeScolaire
from django.db import models

from sis_common.exam_files import (
    PrivateFinancialStorage,
    payment_proof_upload_to,
    validate_payment_proof,
)


class TypeFrais(models.Model):
    """Type de frais (scolarité, inscription, cantine, etc.)."""

    PERIODE_CHOICES = [
        ("unique", "Unique"),
        ("mensuel", "Mensuel"),
        ("trimestriel", "Trimestriel"),
        ("annuel", "Annuel"),
    ]
    annee_scolaire = models.ForeignKey(AnneeScolaire, on_delete=models.CASCADE, related_name="types_frais")
    code = models.CharField(max_length=50)
    libelle = models.CharField(max_length=200)
    montant = models.DecimalField(max_digits=10, decimal_places=2)
    periodicite = models.CharField(max_length=20, choices=PERIODE_CHOICES, default="annuel")
    obligatoire = models.BooleanField(default=True)
    classes = models.ManyToManyField("classes.Classe", blank=True, related_name="types_frais")
    date_limite = models.DateField(null=True, blank=True)
    actif = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("annee_scolaire", "code")]
        verbose_name = "Type de frais"
        verbose_name_plural = "Types de frais"

    def __str__(self):
        return f"{self.libelle} ({self.montant}€)"


class BudgetPrevisionnel(models.Model):
    """Montant prévu pour un poste libre d'une année scolaire, sans suivi des dépenses."""

    annee_scolaire = models.ForeignKey(AnneeScolaire, on_delete=models.PROTECT, related_name="budgets_previsionnels")
    code = models.CharField(max_length=50)
    libelle = models.CharField(max_length=200)
    montant_prevu = models.DecimalField(max_digits=12, decimal_places=2)
    statut = models.CharField(
        max_length=10,
        choices=[("ouvert", "Ouvert"), ("cloture", "Clôturé")],
        default="ouvert",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["annee_scolaire", "code"], name="secondaire_budget_year_code"),
            models.CheckConstraint(condition=models.Q(montant_prevu__gt=0), name="secondaire_budget_positive"),
        ]


class Facture(models.Model):
    """Facture émise pour un élève."""

    STATUT_CHOICES = [
        ("brouillon", "Brouillon"),
        ("emise", "Émise"),
        ("payee", "Payée"),
        ("partielle", "Partiellement payée"),
        ("en_retard", "En retard"),
        ("annulee", "Annulée"),
    ]
    eleve = models.ForeignKey(Eleve, on_delete=models.PROTECT, related_name="factures")
    type_frais = models.ForeignKey(TypeFrais, on_delete=models.PROTECT, related_name="factures")
    numero = models.CharField(max_length=50, unique=True)
    date_emission = models.DateField()
    date_echeance = models.DateField()
    montant = models.DecimalField(max_digits=10, decimal_places=2)
    montant_paye = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    devise = models.CharField(max_length=3, blank=True, default="")
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default="emise")
    note = models.TextField(blank=True)
    pdf_path = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date_emission"]
        indexes = [
            models.Index(fields=["eleve", "statut"]),
            models.Index(fields=["date_echeance"]),
        ]

    def __str__(self):
        return f"Facture {self.numero} - {self.eleve}"

    @property
    def montant_restant(self):
        return self.montant - self.montant_paye


class Paiement(models.Model):
    """Paiement d'une facture."""

    MODE_CHOICES = [
        ("especes", "Espèces"),
        ("cheque", "Chèque"),
        ("virement", "Virement"),
        ("carte", "Carte bancaire"),
        ("mobile_money", "Mobile Money"),
        ("autre", "Autre"),
    ]
    STATUT_CHOICES = [
        ("en_attente", "En attente"),
        ("valide", "Validé"),
        ("echec", "Échec"),
        ("rejete", "Rejeté"),
        ("rembourse", "Remboursé"),
    ]
    facture = models.ForeignKey(Facture, on_delete=models.CASCADE, related_name="paiements")
    numero = models.CharField(max_length=50, unique=True)
    date_paiement = models.DateField()
    montant = models.DecimalField(max_digits=10, decimal_places=2)
    mode = models.CharField(max_length=20, choices=MODE_CHOICES)
    reference_externe = models.CharField(max_length=200, blank=True, help_text="N° chèque, transaction ID...")
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default="en_attente")
    remboursement = models.JSONField(default=dict, blank=True)
    preuve_remboursement = models.FileField(
        upload_to=payment_proof_upload_to,
        storage=PrivateFinancialStorage(),
        validators=[validate_payment_proof],
        null=True,
        blank=True,
    )
    recu_pdf = models.CharField(max_length=500, blank=True)
    preuve_paiement = models.FileField(
        upload_to=payment_proof_upload_to,
        storage=PrivateFinancialStorage(),
        validators=[validate_payment_proof],
        null=True,
        blank=True,
    )
    enregistre_par = models.ForeignKey(
        "utilisateurs.Utilisateur",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="paiements_enregistres",
    )
    verifie_par = models.ForeignKey(
        "utilisateurs.Utilisateur",
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
        indexes = [
            models.Index(fields=["facture", "statut"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["mode", "reference_externe"],
                condition=models.Q(statut__in=["valide", "rembourse"]) & ~models.Q(reference_externe=""),
                name="secondaire_payment_reference_once",
            ),
            models.UniqueConstraint(
                fields=["reference_externe"],
                condition=models.Q(mode="carte", statut__in=["valide", "rembourse"]) & ~models.Q(reference_externe=""),
                name="secondaire_card_reference_once",
            ),
        ]

    def __str__(self):
        return f"Paiement {self.numero} - {self.montant} {self.facture.devise or '(devise non configurée)'}"
