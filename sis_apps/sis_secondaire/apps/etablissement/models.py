"""Models for etablissement (SIS Secondaire)."""

from django.db import models
from django_tenants.models import DomainMixin, TenantMixin


class Etablissement(TenantMixin):
    """Établissement scolaire (collège/lycée) — base du multi-tenant."""

    TYPE_CHOICES = [
        ("college", "Collège"),
        ("lycee", "Lycée"),
        ("lycee_technique", "Lycée technique"),
        ("lycee_professionnel", "Lycée professionnel"),
    ]

    nom = models.CharField(max_length=200)
    type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    uai = models.CharField(max_length=20, blank=True, help_text="Identifiant national")
    adresse = models.TextField()
    code_postal = models.CharField(max_length=10)
    ville = models.CharField(max_length=100)
    pays = models.CharField(max_length=100, default="France")
    telephone = models.CharField(max_length=20)
    email = models.EmailField()
    site_web = models.URLField(blank=True)
    logo = models.ImageField(upload_to="logos/", null=True, blank=True)
    devise = models.CharField(max_length=200, blank=True)
    ministere_tutelle = models.CharField(max_length=200, blank=True)
    systeme_periodes = models.CharField(
        max_length=20,
        choices=[
            ("trimestre", "Trimestre"),
            ("semestre", "Semestre"),
            ("quadrimestre", "Quadrimestre"),
        ],
        default="trimestre",
    )
    date_creation = models.DateTimeField(auto_now_add=True)
    actif = models.BooleanField(default=True)
    auto_create_schema = True

    class Meta:
        verbose_name = "Établissement"
        verbose_name_plural = "Établissements"

    def __str__(self):
        return f"{self.nom} ({self.get_type_display()})"


class Domain(DomainMixin):
    """Domaine associé à un établissement."""

    pass


class AnneeScolaire(models.Model):
    """Année scolaire d'un établissement."""

    etablissement = models.ForeignKey(
        Etablissement, on_delete=models.CASCADE, related_name="annees_scolaires"
    )
    libelle = models.CharField(max_length=50, help_text="Ex: 2026-2027")
    date_debut = models.DateField()
    date_fin = models.DateField()
    en_cours = models.BooleanField(default=False)
    cloturee = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("etablissement", "libelle")]
        ordering = ["-date_debut"]

    def __str__(self):
        return self.libelle


class Periode(models.Model):
    """Période (trimestre, semestre, etc.)."""

    TYPE_CHOICES = [
        ("trimestre", "Trimestre"),
        ("semestre", "Semestre"),
        ("quadrimestre", "Quadrimestre"),
        ("sequence", "Séquence"),
    ]
    annee_scolaire = models.ForeignKey(
        AnneeScolaire, on_delete=models.CASCADE, related_name="periodes"
    )
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    numero = models.PositiveSmallIntegerField()
    libelle = models.CharField(max_length=50, blank=True)
    date_debut = models.DateField()
    date_fin = models.DateField()
    cloturee = models.BooleanField(default=False)

    class Meta:
        unique_together = [("annee_scolaire", "type", "numero")]
        ordering = ["annee_scolaire", "numero"]

    def __str__(self):
        return (
            f"{self.get_type_display()} {self.numero} - {self.annee_scolaire.libelle}"
        )


class Niveau(models.Model):
    """Niveau scolaire (6e, 5e, 2nde, etc.)."""

    CODE_CHOICES = [
        ("6e", "6ème"),
        ("5e", "5ème"),
        ("4e", "4ème"),
        ("3e", "3ème"),
        ("2nde", "2nde"),
        ("1ere", "1ère"),
        ("tale", "Terminale"),
        ("2nde_pro", "2nde Pro"),
        ("1ere_pro", "1ère Pro"),
        ("tale_pro", "Terminale Pro"),
    ]
    etablissement = models.ForeignKey(
        Etablissement, on_delete=models.CASCADE, related_name="niveaux"
    )
    code = models.CharField(max_length=20)
    libelle = models.CharField(max_length=100)
    ordre = models.PositiveSmallIntegerField(default=0)
    cycle = models.CharField(
        max_length=20,
        choices=[("college", "Collège"), ("lycee", "Lycée")],
        blank=True,
    )

    class Meta:
        unique_together = [("etablissement", "code")]
        ordering = ["ordre"]

    def __str__(self):
        return f"{self.libelle}"
