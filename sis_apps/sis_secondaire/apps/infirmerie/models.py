"""Models for infirmerie (SIS Secondaire)."""

from apps.eleves.models import Eleve
from apps.utilisateurs.models import Utilisateur
from django.db import models

from sis_common.encryption import EncryptedCharField, EncryptedJSONField, EncryptedTextField


class DossierMedical(models.Model):
    """Dossier médical d'un élève (accès restreint)."""

    eleve = models.OneToOneField(
        Eleve, on_delete=models.CASCADE, related_name="dossier_medical"
    )
    groupe_sanguin = EncryptedCharField(max_length=5, blank=True)
    allergies = EncryptedJSONField(default=list, blank=True)
    maladies_chroniques = EncryptedJSONField(default=list, blank=True)
    traitements = EncryptedTextField(blank=True)
    vaccinations = EncryptedJSONField(default=list, blank=True)
    medecin_traitant = models.CharField(max_length=200, blank=True)
    telephone_medecin = models.CharField(max_length=20, blank=True)
    observations = EncryptedTextField(blank=True)
    date_derniere_visite = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Dossier médical"
        verbose_name_plural = "Dossiers médicaux"

    def __str__(self):
        return f"Dossier médical {self.eleve}"


class VisiteInfirmerie(models.Model):
    """Visite d'un élève à l'infirmerie."""

    ORIENTATION_CHOICES = [
        ("retour_cours", "Retour en cours"),
        ("sortie", "Sortie autorisée"),
        ("urgence", "Urgence médicale"),
        ("parents", "Parents appelés"),
        ("hospitalisation", "Hospitalisation"),
    ]
    eleve = models.ForeignKey(
        Eleve, on_delete=models.CASCADE, related_name="visites_infirmerie"
    )
    date = models.DateTimeField()
    heure_arrivee = models.TimeField()
    heure_sortie = models.TimeField(null=True, blank=True)
    motif = models.CharField(max_length=200)
    symptomes = EncryptedTextField(blank=True)
    soins = EncryptedTextField(blank=True)
    traitement_administre = EncryptedTextField(blank=True)
    orientation = models.CharField(
        max_length=30, choices=ORIENTATION_CHOICES, default="retour_cours"
    )
    infirmier = models.ForeignKey(
        Utilisateur,
        on_delete=models.PROTECT,
        related_name="visites_infirmerie",
        limit_choices_to={"role": "infirmier"},
    )
    parents_prevenus = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Visite infirmerie"
        verbose_name_plural = "Visites infirmerie"
        ordering = ["-date"]

    def __str__(self):
        return f"Visite {self.eleve} - {self.date}"


class StockMedicament(models.Model):
    """Stock de médicaments et matériel."""

    nom = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    quantite = models.PositiveIntegerField(default=0)
    seuil_alerte = models.PositiveIntegerField(default=5)
    unite = models.CharField(max_length=20, default="unité")
    date_peremption = models.DateField(null=True, blank=True)
    numero_lot = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Stock médicament"
        verbose_name_plural = "Stock médicaments"

    def __str__(self):
        return f"{self.nom} ({self.quantite})"

    @property
    def en_alerte(self):
        return self.quantite <= self.seuil_alerte
