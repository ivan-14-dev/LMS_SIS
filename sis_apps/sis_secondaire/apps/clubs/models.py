"""Models for clubs (SIS Secondaire)."""
from django.db import models
from apps.eleves.models import Eleve
from apps.utilisateurs.models import Utilisateur


class Club(models.Model):
    """Club / activité périscolaire."""
    TYPE_CHOICES = [
        ("sportif", "Sportif"),
        ("culturel", "Culturel"),
        ("scientifique", "Scientifique"),
        ("artistique", "Artistique"),
        ("citoyen", "Citoyen"),
        ("autre", "Autre"),
    ]
    nom = models.CharField(max_length=200)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    description = models.TextField()
    responsable = models.ForeignKey(
        Utilisateur, on_delete=models.PROTECT, related_name="clubs_responsable"
    )
    salle = models.CharField(max_length=100, blank=True)
    horaires = models.CharField(max_length=200, help_text="Ex: Mercredi 14h-16h")
    capacite = models.PositiveSmallIntegerField(default=30)
    image = models.ImageField(upload_to="clubs/", null=True, blank=True)
    couleur = models.CharField(max_length=7, default="#3B82F6")
    date_creation = models.DateField()
    actif = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Club"
        verbose_name_plural = "Clubs"
        ordering = ["nom"]

    def __str__(self):
        return self.nom


class MembreClub(models.Model):
    """Membre d'un club."""
    club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name="membres")
    eleve = models.ForeignKey(Eleve, on_delete=models.CASCADE, related_name="clubs_membre")
    date_inscription = models.DateField(auto_now_add=True)
    statut = models.CharField(
        max_length=20,
        choices=[("actif", "Actif"), ("inactif", "Inactif"), ("suspendu", "Suspendu")],
        default="actif",
    )

    class Meta:
        unique_together = [("club", "eleve")]
        verbose_name = "Membre de club"
        verbose_name_plural = "Membres de club"

    def __str__(self):
        return f"{self.eleve} - {self.club.nom}"


class SeanceClub(models.Model):
    """Séance d'un club."""
    club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name="seances")
    date = models.DateField()
    heure_debut = models.TimeField()
    heure_fin = models.TimeField()
    activite = models.TextField()
    presents = models.ManyToManyField(Eleve, related_name="seances_presence", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Séance de club"
        verbose_name_plural = "Séances de club"
        ordering = ["-date"]

    def __str__(self):
        return f"{self.club.nom} - {self.date}"
