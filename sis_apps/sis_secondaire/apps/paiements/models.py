"""Models for paiements (SIS Secondaire)."""
from django.db import models
from apps.eleves.models import Eleve
from apps.etablissement.models import AnneeScolaire


class TypeFrais(models.Model):
    """Type de frais (scolarité, inscription, cantine, etc.)."""
    PERIODE_CHOICES = [
        ("unique", "Unique"),
        ("mensuel", "Mensuel"),
        ("trimestriel", "Trimestriel"),
        ("annuel", "Annuel"),
    ]
    annee_scolaire = models.ForeignKey(
        AnneeScolaire, on_delete=models.CASCADE, related_name="types_frais"
    )
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
        ("rembourse", "Remboursé"),
    ]
    facture = models.ForeignKey(Facture, on_delete=models.CASCADE, related_name="paiements")
    numero = models.CharField(max_length=50, unique=True)
    date_paiement = models.DateField()
    montant = models.DecimalField(max_digits=10, decimal_places=2)
    mode = models.CharField(max_length=20, choices=MODE_CHOICES)
    reference_externe = models.CharField(max_length=200, blank=True, help_text="N° chèque, transaction ID...")
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default="valide")
    recu_pdf = models.CharField(max_length=500, blank=True)
    enregistre_par = models.ForeignKey(
        "utilisateurs.Utilisateur", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="paiements_enregistres",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_paiement"]
        indexes = [
            models.Index(fields=["facture", "statut"]),
        ]

    def __str__(self):
        return f"Paiement {self.numero} - {self.montant}€"
