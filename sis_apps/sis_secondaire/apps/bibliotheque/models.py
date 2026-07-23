"""Models for bibliotheque (SIS Secondaire)."""
from django.db import models
from apps.utilisateurs.models import Utilisateur


class Livre(models.Model):
    """Référence d'un livre."""
    isbn = models.CharField(max_length=20, blank=True)
    titre = models.CharField(max_length=300)
    auteurs = models.CharField(max_length=500)
    editeur = models.CharField(max_length=200, blank=True)
    annee = models.PositiveSmallIntegerField(null=True, blank=True)
    categorie = models.CharField(max_length=100, blank=True)
    mots_cles = models.JSONField(default=list, blank=True)
    resume = models.TextField(blank=True)
    image_couverture = models.URLField(blank=True)
    cote = models.CharField(max_length=50, blank=True)
    nombre_exemplaires = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Livre"
        verbose_name_plural = "Livres"
        ordering = ["titre"]

    def __str__(self):
        return f"{self.titre} - {self.auteurs}"


class Exemplaire(models.Model):
    """Exemplaire physique."""
    ETAT_CHOICES = [
        ("neuf", "Neuf"),
        ("bon", "Bon"),
        ("use", "Usé"),
        ("détérioré", "Détérioré"),
        ("perdu", "Perdu"),
    ]
    livre = models.ForeignKey(Livre, on_delete=models.CASCADE, related_name="exemplaires")
    code_barre = models.CharField(max_length=50, unique=True)
    etat = models.CharField(max_length=20, choices=ETAT_CHOICES, default="bon")
    localisation = models.CharField(max_length=200, blank=True)
    date_acquisition = models.DateField(null=True, blank=True)
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
    ]
    exemplaire = models.ForeignKey(Exemplaire, on_delete=models.PROTECT, related_name="emprunts")
    emprunteur = models.ForeignKey(Utilisateur, on_delete=models.PROTECT, related_name="emprunts")
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
    livre = models.ForeignKey(Livre, on_delete=models.CASCADE, related_name="reservations")
    utilisateur = models.ForeignKey(Utilisateur, on_delete=models.CASCADE, related_name="reservations_biblio")
    date_reservation = models.DateTimeField(auto_now_add=True)
    statut = models.CharField(
        max_length=20,
        choices=[("en_attente", "En attente"), ("disponible", "Disponible"), ("annulee", "Annulée")],
        default="en_attente",
    )

    class Meta:
        verbose_name = "Réservation"
        verbose_name_plural = "Réservations"

    def __str__(self):
        return f"{self.utilisateur} - {self.livre.titre}"
