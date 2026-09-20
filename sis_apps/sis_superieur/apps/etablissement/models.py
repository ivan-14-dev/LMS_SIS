"""Models for etablissement (SIS Supérieur)."""

from django.core.validators import RegexValidator
from django.db import models
from django_tenants.models import DomainMixin, TenantMixin
from sis_common.establishments import (
    default_establishment_features,
    default_live_configuration,
    validate_establishment_features,
    validate_live_configuration,
    validate_timezone,
)
from sis_common.academic_configuration import (
    default_academic_configuration,
    validate_academic_configuration,
)


class Universite(TenantMixin):
    """Université / Grande école / Institut — base du multi-tenant."""

    TYPE_CHOICES = [
        ("universite_publique", "Université publique"),
        ("universite_privee", "Université privée"),
        ("grande_ecole", "Grande école"),
        ("institut", "Institut supérieur"),
        ("ecole_doctorale", "École doctorale"),
        ("autre", "Autre établissement"),
    ]
    nom = models.CharField(max_length=200)
    type = models.CharField(max_length=100)
    type_personnalise = models.CharField(
        max_length=100,
        blank=True,
        help_text="Libellé utilisé lorsque le type d'établissement est « autre ».",
    )
    sigle = models.CharField(max_length=20, blank=True)
    ministere_tutelle = models.CharField(max_length=200, blank=True)
    uai = models.CharField(max_length=20, blank=True)
    adresse = models.TextField()
    code_postal = models.CharField(max_length=10)
    ville = models.CharField(max_length=100)
    pays = models.CharField(max_length=100, default="France")
    telephone = models.CharField(max_length=20)
    email = models.EmailField()
    site_web = models.URLField(blank=True)
    logo = models.ImageField(upload_to="logos/", null=True, blank=True)
    couleur_primaire = models.CharField(
        max_length=7,
        default="#0A3055",
        validators=[
            RegexValidator(
                r"^#[0-9A-Fa-f]{6}$",
                "Utilisez une couleur hexadécimale, par exemple #0A3055.",
            )
        ],
    )
    couleur_secondaire = models.CharField(
        max_length=7,
        default="#FFFFFF",
        validators=[
            RegexValidator(
                r"^#[0-9A-Fa-f]{6}$",
                "Utilisez une couleur hexadécimale, par exemple #FFFFFF.",
            )
        ],
    )
    fuseau_horaire = models.CharField(
        max_length=64, default="UTC", validators=[validate_timezone]
    )
    fonctionnalites = models.JSONField(
        default=default_establishment_features,
        validators=[validate_establishment_features],
    )
    configuration_visio = models.JSONField(
        default=default_live_configuration,
        validators=[validate_live_configuration],
    )
    configuration_academique = models.JSONField(
        default=default_academic_configuration,
        validators=[validate_academic_configuration],
    )
    systeme_notation = models.CharField(max_length=20, default="LMD")
    credits_annee = models.PositiveSmallIntegerField(default=60)
    accreditations = models.JSONField(default=list, blank=True)
    conventions_internationales = models.JSONField(default=list, blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    actif = models.BooleanField(default=True)
    auto_create_schema = True

    class Meta:
        verbose_name = "Université"
        verbose_name_plural = "Universités"

    def __str__(self):
        return self.nom

    def get_type_display(self):
        return dict(self.TYPE_CHOICES).get(self.type, self.type)


class Domain(DomainMixin):
    """Domaine de l'université."""

    pass


class AnneeUniversitaire(models.Model):
    """Année universitaire."""

    universite = models.ForeignKey(
        Universite, on_delete=models.CASCADE, related_name="annees_universitaires"
    )
    libelle = models.CharField(max_length=50, help_text="Ex: 2026-2027")
    date_debut = models.DateField()
    date_fin = models.DateField()
    en_cours = models.BooleanField(default=False)
    cloturee = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("universite", "libelle")]
        ordering = ["-date_debut"]

    def __str__(self):
        return self.libelle


class Semestre(models.Model):
    """Semestre universitaire."""

    TYPE_CHOICES = [
        ("impair", "Semestre impair (S1, S3, S5)"),
        ("pair", "Semestre pair (S2, S4, S6)"),
        ("unique", "Semestre unique"),
    ]
    annee_universitaire = models.ForeignKey(
        AnneeUniversitaire, on_delete=models.CASCADE, related_name="semestres"
    )
    numero = models.PositiveSmallIntegerField()
    type = models.CharField(max_length=50)
    date_debut = models.DateField()
    date_fin = models.DateField()
    cloture = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("annee_universitaire", "numero")]
        ordering = ["annee_universitaire", "numero"]

    def __str__(self):
        return f"S{self.numero} - {self.annee_universitaire.libelle}"

    def get_type_display(self):
        return dict(self.TYPE_CHOICES).get(self.type, self.type)
