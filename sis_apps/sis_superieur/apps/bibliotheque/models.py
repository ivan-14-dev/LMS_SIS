"""Models for bibliotheque (SIS Supérieur)."""

from apps.utilisateurs.models import Utilisateur
from django.db import models


class Livre(models.Model):
    """Référence d'un livre / document."""

    isbn = models.CharField(max_length=20, blank=True)
    titre = models.CharField(max_length=300)
    sous_titre = models.CharField(max_length=300, blank=True)
    auteurs = models.CharField(max_length=500, help_text="Auteur1; Auteur2")
    editeur = models.CharField(max_length=200, blank=True)
    annee_publication = models.PositiveSmallIntegerField(null=True, blank=True)
    langue = models.CharField(max_length=10, default="fr")
    categorie = models.CharField(max_length=100, blank=True)
    mots_cles = models.JSONField(default=list, blank=True)
    resume = models.TextField(blank=True)
    image_couverture = models.URLField(blank=True)
    cote = models.CharField(max_length=50, blank=True, help_text="Ex: 004.123 DUP")
    nombre_exemplaires = models.PositiveIntegerField(default=1)
    ressource_numerique = models.FileField(
        upload_to="bibliotheque/numerique/", null=True, blank=True
    )
    url_externe = models.URLField(blank=True, help_text="Pour ebooks externes")
    base_donnees = models.CharField(
        max_length=200, blank=True, help_text="Ex: ScienceDirect, JSTOR"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Livre"
        verbose_name_plural = "Livres"
        ordering = ["titre"]

    def __str__(self):
        return f"{self.titre} - {self.auteurs}"


class Exemplaire(models.Model):
    """Exemplaire physique d'un livre."""

    ETAT_CHOICES = [
        ("neuf", "Neuf"),
        ("bon", "Bon état"),
        ("use", "Usé"),
        ("détérioré", "Détérioré"),
        ("perdu", "Perdu"),
    ]
    livre = models.ForeignKey(
        Livre, on_delete=models.CASCADE, related_name="exemplaires"
    )
    code_barre = models.CharField(max_length=50, unique=True)
    etat = models.CharField(max_length=20, choices=ETAT_CHOICES, default="bon")
    localisation = models.CharField(
        max_length=200, blank=True, help_text="Salle, rayon, étagère"
    )
    date_acquisition = models.DateField(null=True, blank=True)
    prix_acquisition = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Exemplaire"
        verbose_name_plural = "Exemplaires"

    def __str__(self):
        return f"{self.code_barre} - {self.livre.titre}"


class Emprunt(models.Model):
    """Emprunt d'un livre par un utilisateur."""

    STATUT_CHOICES = [
        ("en_cours", "En cours"),
        ("rendu", "Rendu"),
        ("en_retard", "En retard"),
        ("perdu", "Perdu"),
        ("renouvele", "Renouvelé"),
    ]
    exemplaire = models.ForeignKey(
        Exemplaire, on_delete=models.PROTECT, related_name="emprunts"
    )
    emprunteur = models.ForeignKey(
        Utilisateur, on_delete=models.PROTECT, related_name="emprunts"
    )
    date_emprunt = models.DateField()
    date_retour_prevue = models.DateField()
    date_retour_reelle = models.DateField(null=True, blank=True)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default="en_cours")
    nb_renouvellements = models.PositiveSmallIntegerField(default=0)
    penalite = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Emprunt"
        verbose_name_plural = "Emprunts"
        ordering = ["-date_emprunt"]

    def __str__(self):
        return f"{self.emprunteur} - {self.exemplaire}"


class Reservation(models.Model):
    """Réservation d'un livre."""

    livre = models.ForeignKey(
        Livre, on_delete=models.CASCADE, related_name="reservations"
    )
    utilisateur = models.ForeignKey(
        Utilisateur, on_delete=models.CASCADE, related_name="reservations"
    )
    date_reservation = models.DateTimeField(auto_now_add=True)
    statut = models.CharField(
        max_length=20,
        choices=[
            ("en_attente", "En attente"),
            ("disponible", "Disponible"),
            ("annulee", "Annulée"),
            ("recuperee", "Récupérée"),
        ],
        default="en_attente",
    )
    date_notification = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Réservation"
        verbose_name_plural = "Réservations"

    def __str__(self):
        return f"{self.utilisateur} - {self.livre.titre}"


class SalleTravail(models.Model):
    """Salle de travail en groupe à la BU."""

    nom = models.CharField(max_length=100)
    capacite = models.PositiveIntegerField(default=4)
    equipements = models.JSONField(
        default=list, blank=True, help_text='["tableau", "ecran", "wifi"]'
    )
    disponible = models.BooleanField(default=True)
    batiment = models.CharField(max_length=100, blank=True)
    etage = models.CharField(max_length=20, blank=True)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name = "Salle de travail"
        verbose_name_plural = "Salles de travail"

    def __str__(self):
        return self.nom


class ReservationSalle(models.Model):
    """Réservation d'une salle de travail BU."""

    salle = models.ForeignKey(
        SalleTravail, on_delete=models.CASCADE, related_name="reservations"
    )
    utilisateur = models.ForeignKey(
        Utilisateur, on_delete=models.CASCADE, related_name="reservations_salles"
    )
    date = models.DateField()
    heure_debut = models.TimeField()
    heure_fin = models.TimeField()
    motif = models.CharField(max_length=200, blank=True)
    nb_personnes = models.PositiveSmallIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Réservation salle"
        verbose_name_plural = "Réservations salle"
        ordering = ["date", "heure_debut"]

    def __str__(self):
        return f"{self.salle} - {self.date}"
