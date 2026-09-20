"""Models for utilisateurs (SIS Secondaire)."""

from apps.etablissement.models import Etablissement
from django.contrib.auth.models import AbstractUser
from django.db import models


class Utilisateur(AbstractUser):
    """Utilisateur de la plateforme (élève, parent, enseignant, personnel)."""

    ROLE_CHOICES = [
        ("super_admin", "Super administrateur"),
        ("direction", "Direction"),
        ("responsable_pedagogique", "Responsable pédagogique"),
        ("enseignant", "Enseignant"),
        ("personnel_administratif", "Personnel administratif"),
        ("comptable", "Comptable"),
        ("bibliothecaire", "Bibliothécaire"),
        ("infirmier", "Infirmier"),
        ("surveillant", "Surveillant"),
        ("vie_scolaire", "Vie scolaire"),
        ("eleve", "Élève"),
        ("parent", "Parent"),
    ]
    etablissement = models.ForeignKey(
        Etablissement,
        on_delete=models.CASCADE,
        related_name="utilisateurs",
        null=True,
        blank=True,
    )
    role = models.CharField(max_length=40, choices=ROLE_CHOICES, default="eleve")
    telephone = models.CharField(max_length=20, blank=True)
    adresse = models.TextField(blank=True)
    photo = models.ImageField(upload_to="photos/", null=True, blank=True)
    langue = models.CharField(max_length=10, default="fr")
    mfa_active = models.BooleanField(default=False)
    mfa_secret = models.CharField(max_length=100, blank=True)
    doit_changer_mdp = models.BooleanField(default=False)
    derniere_connexion = models.DateTimeField(null=True, blank=True)
    preferences_notification = models.JSONField(default=dict, blank=True)
    attributs_acces = models.JSONField(
        default=dict,
        blank=True,
        help_text="Contraintes ABAC par permission (classes, matières, années, etc.).",
    )

    class Meta:
        verbose_name = "Utilisateur"
        verbose_name_plural = "Utilisateurs"

    def __str__(self):
        return f"{self.get_full_name()} ({self.get_role_display()})"

    @property
    def is_eleve(self):
        return self.role == "eleve"

    @property
    def is_enseignant(self):
        return self.role == "enseignant"

    @property
    def is_parent(self):
        return self.role == "parent"
