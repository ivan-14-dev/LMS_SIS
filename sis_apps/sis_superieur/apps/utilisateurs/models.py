"""Models for utilisateurs (SIS Supérieur)."""
from django.contrib.auth.models import AbstractUser
from django.db import models


class Utilisateur(AbstractUser):
    """Utilisateur de la plateforme universitaire."""
    ROLE_CHOICES = [
        ("super_admin", "Super administrateur"),
        ("president", "Président d'université"),
        ("vice_president", "Vice-président"),
        ("doyen", "Doyen de faculté"),
        ("directeur_dept", "Directeur de département"),
        ("responsable_formation", "Responsable de formation"),
        ("directeur_etudes", "Directeur des études"),
        ("enseignant", "Enseignant"),
        ("chercheur", "Chercheur"),
        ("personnel_administratif", "Personnel administratif"),
        ("scolarite", "Service scolarité"),
        ("service_social", "Service social"),
        ("service_ri", "Service relations internationales"),
        ("bibliothecaire", "Bibliothécaire"),
        ("comptable", "Comptable"),
        ("etudiant", "Étudiant"),
        ("doctorant", "Doctorant"),
        ("parent", "Parent"),
    ]
    etablissement = models.ForeignKey(
        "etablissement.Universite", on_delete=models.CASCADE,
        related_name="utilisateurs", null=True, blank=True,
    )
    role = models.CharField(max_length=40, choices=ROLE_CHOICES, default="etudiant")
    numero_etudiant = models.CharField(max_length=50, blank=True)
    numero_enseignant = models.CharField(max_length=50, blank=True)
    telephone = models.CharField(max_length=20, blank=True)
    adresse = models.TextField(blank=True)
    photo = models.ImageField(upload_to="photos/", null=True, blank=True)
    langue = models.CharField(max_length=10, default="fr")
    mfa_active = models.BooleanField(default=False)
    mfa_secret = models.CharField(max_length=100, blank=True)
    doit_changer_mdp = models.BooleanField(default=False)
    derniere_connexion = models.DateTimeField(null=True, blank=True)
    preferences_notification = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = "Utilisateur"
        verbose_name_plural = "Utilisateurs"

    def __str__(self):
        return f"{self.get_full_name()} ({self.get_role_display()})"

    @property
    def is_etudiant(self):
        return self.role in ("etudiant", "doctorant")

    @property
    def is_enseignant(self):
        return self.role in ("enseignant", "chercheur")

    @property
    def is_admin(self):
        return self.role in ("president", "vice_president", "doyen", "directeur_dept", "scolarite")
