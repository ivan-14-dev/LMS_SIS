"""Models for entreprises (SIS Supérieur)."""
from django.db import models
from apps.utilisateurs.models import Utilisateur


class Entreprise(models.Model):
    """Entreprise / Organisation d'accueil (stages, alternance)."""
    TYPE_CHOICES = [
        ("SA", "SA"),
        ("SARL", "SARL"),
        ("SAS", "SAS"),
        ("EURL", "EURL"),
        ("SCI", "SCI"),
        ("Association", "Association"),
        ("EPI", "Établissement public"),
        ("Etranger", "Entreprise étrangère"),
    ]
    SECTEUR_CHOICES = [
        ("informatique", "Informatique / Tech"),
        ("industrie", "Industrie"),
        ("finance", "Finance / Banque"),
        ("conseil", "Conseil"),
        ("sante", "Santé"),
        ("education", "Éducation"),
        ("energie", "Énergie"),
        ("agro", "Agroalimentaire"),
        ("bTP", "BTP"),
        ("autre", "Autre"),
    ]
    raison_sociale = models.CharField(max_length=200)
    type = models.CharField(max_length=30, choices=TYPE_CHOICES, default="SARL")
    siret = models.CharField(max_length=20, blank=True)
    siren = models.CharField(max_length=10, blank=True)
    tva_intracommunautaire = models.CharField(max_length=20, blank=True)
    secteur = models.CharField(max_length=30, choices=SECTEUR_CHOICES, default="autre")
    description = models.TextField(blank=True)
    site_web = models.URLField(blank=True)
    adresse = models.TextField()
    code_postal = models.CharField(max_length=10)
    ville = models.CharField(max_length=100)
    pays = models.CharField(max_length=100, default="France")
    telephone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    logo = models.ImageField(upload_to="entreprises/", null=True, blank=True)
    taille = models.CharField(max_length=20, blank=True, help_text="TPE, PME, ETI, GE")
    actif = models.BooleanField(default=True)
    cree_le = models.DateTimeField(auto_now_add=True)
    modifie_le = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Entreprise"
        verbose_name_plural = "Entreprises"
        ordering = ["raison_sociale"]

    def __str__(self):
        return self.raison_sociale


class ContactEntreprise(models.Model):
    """Contact dans une entreprise (RH, tuteur, etc.)."""
    ROLE_CHOICES = [
        ("rh", "RH"),
        ("tuteur", "Tuteur de stage"),
        ("responsable", "Responsable"),
        ("dirigeant", "Dirigeant"),
        ("autre", "Autre"),
    ]
    entreprise = models.ForeignKey(Entreprise, on_delete=models.CASCADE, related_name="contacts")
    nom = models.CharField(max_length=200)
    prenom = models.CharField(max_length=200)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="tuteur")
    fonction = models.CharField(max_length=200, blank=True)
    email = models.EmailField()
    telephone = models.CharField(max_length=20)
    user = models.OneToOneField(
        Utilisateur, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="contact_entreprise_profile",
    )
    actif = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Contact entreprise"
        verbose_name_plural = "Contacts entreprise"

    def __str__(self):
        return f"{self.prenom} {self.nom} ({self.entreprise})"
