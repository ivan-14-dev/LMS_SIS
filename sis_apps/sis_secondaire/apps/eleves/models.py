"""Models for eleves (SIS Secondaire)."""

from apps.classes.models import Classe
from apps.etablissement.models import AnneeScolaire, Etablissement
from apps.utilisateurs.models import Utilisateur
from django.db import models


class Eleve(models.Model):
    """Élève inscrit dans l'établissement."""

    STATUT_CHOICES = [
        ("inscrit", "Inscrit"),
        ("redoublant", "Redoublant"),
        ("sortant", "Sortant"),
        ("transfere", "Transféré"),
        ("diplome", "Diplômé"),
        ("abandon", "Abandon"),
    ]
    SEXE_CHOICES = [("M", "Masculin"), ("F", "Féminin")]

    etablissement = models.ForeignKey(
        Etablissement, on_delete=models.CASCADE, related_name="eleves"
    )
    user = models.OneToOneField(
        Utilisateur, on_delete=models.CASCADE, related_name="eleve_profile"
    )
    matricule = models.CharField(max_length=50, unique=True)
    date_naissance = models.DateField()
    lieu_naissance = models.CharField(max_length=200)
    sexe = models.CharField(max_length=1, choices=SEXE_CHOICES)
    nationalite = models.CharField(max_length=100, default="Française")
    ine = models.CharField(
        max_length=20, blank=True, help_text="Identifiant National Élève"
    )
    adresse = models.TextField(blank=True)
    code_postal = models.CharField(max_length=10, blank=True)
    ville = models.CharField(max_length=100, blank=True)
    classe_actuelle = models.ForeignKey(
        Classe,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="eleves_actuels",
    )
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default="inscrit")
    date_inscription = models.DateField()
    motif_sortie = models.TextField(blank=True)
    photo = models.ImageField(upload_to="eleves/", null=True, blank=True)
    qr_code = models.CharField(max_length=200, blank=True)
    allergies = models.TextField(blank=True)
    contact_urgence_nom = models.CharField(max_length=200, blank=True)
    contact_urgence_tel = models.CharField(max_length=20, blank=True)
    bourse = models.BooleanField(default=False)
    transport = models.BooleanField(default=False)
    cantine = models.BooleanField(default=False)
    interne = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["user__last_name", "user__first_name"]
        indexes = [
            models.Index(fields=["matricule"]),
            models.Index(fields=["statut"]),
            models.Index(fields=["classe_actuelle"]),
        ]

    def __str__(self):
        return f"{self.matricule} - {self.user.get_full_name()}"


class Inscription(models.Model):
    """Inscription annuelle d'un élève dans une classe."""

    STATUT_CHOICES = [
        ("en_cours", "En cours"),
        ("validee", "Validée"),
        ("refusee", "Refusée"),
        ("annulee", "Annulée"),
    ]

    eleve = models.ForeignKey(
        Eleve, on_delete=models.CASCADE, related_name="inscriptions"
    )
    classe = models.ForeignKey(
        Classe, on_delete=models.PROTECT, related_name="inscriptions"
    )
    annee_scolaire = models.ForeignKey(
        AnneeScolaire, on_delete=models.PROTECT, related_name="inscriptions"
    )
    date_inscription = models.DateField()
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default="en_cours")
    motif = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("eleve", "annee_scolaire")]
        ordering = ["-annee_scolaire__date_debut"]

    def __str__(self):
        return f"{self.eleve} → {self.classe} ({self.annee_scolaire})"


class Tuteur(models.Model):
    """Parent ou tuteur d'un élève."""

    LIEN_CHOICES = [
        ("pere", "Père"),
        ("mere", "Mère"),
        ("tuteur_legal", "Tuteur légal"),
        ("grand_parent", "Grand-parent"),
        ("autre", "Autre"),
    ]

    etablissement = models.ForeignKey(
        Etablissement, on_delete=models.CASCADE, related_name="tuteurs"
    )
    user = models.OneToOneField(
        Utilisateur,
        on_delete=models.CASCADE,
        related_name="tuteur_profile",
        null=True,
        blank=True,
    )
    nom = models.CharField(max_length=200)
    prenom = models.CharField(max_length=200)
    lien_parente = models.CharField(max_length=20, choices=LIEN_CHOICES)
    telephone = models.CharField(max_length=20)
    telephone_2 = models.CharField(max_length=20, blank=True)
    email = models.EmailField()
    profession = models.CharField(max_length=200, blank=True)
    adresse = models.TextField(blank=True)
    autorise_sortie = models.BooleanField(default=True)
    autorise_photos = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.prenom} {self.nom} ({self.get_lien_parente_display()})"


class EleveTuteur(models.Model):
    """Lien entre un élève et ses tuteurs."""

    eleve = models.ForeignKey(
        Eleve, on_delete=models.CASCADE, related_name="tuteurs_lies"
    )
    tuteur = models.ForeignKey(
        Tuteur, on_delete=models.CASCADE, related_name="enfants_lies"
    )
    est_payeur = models.BooleanField(default=False)
    est_contact_urgence = models.BooleanField(default=True)
    autorise_acces_portail = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("eleve", "tuteur")]

    def __str__(self):
        return f"{self.eleve} ← {self.tuteur}"
