"""Models for formations et parcours (SIS Supérieur)."""

from apps.structure.models import Departement, EcoleDoctorale
from apps.utilisateurs.models import Utilisateur
from django.db import models


class Formation(models.Model):
    """Formation (licence, master, doctorat, etc.)."""

    TYPE_CHOICES = [
        ("licence", "Licence"),
        ("master", "Master"),
        ("doctorat", "Doctorat"),
        ("du", "Diplôme universitaire"),
        ("certificat", "Certificat"),
        ("ingenieur", "Diplôme d'ingénieur"),
        ("commerce", "Diplôme de commerce"),
    ]
    NIVEAU_CHOICES = [
        ("L1", "Licence 1"),
        ("L2", "Licence 2"),
        ("L3", "Licence 3"),
        ("M1", "Master 1"),
        ("M2", "Master 2"),
        ("D1", "Doctorat 1"),
        ("D2", "Doctorat 2"),
        ("D3", "Doctorat 3"),
    ]
    REGIME_CHOICES = [
        ("formation_initiale", "Formation initiale"),
        ("formation_continue", "Formation continue"),
        ("alternance", "Alternance"),
        ("apprentissage", "Apprentissage"),
    ]

    departement = models.ForeignKey(
        Departement,
        on_delete=models.CASCADE,
        related_name="formations",
        null=True,
        blank=True,
    )
    ecole_doctorale = models.ForeignKey(
        EcoleDoctorale,
        on_delete=models.CASCADE,
        related_name="formations",
        null=True,
        blank=True,
    )
    nom = models.CharField(max_length=200)
    code = models.CharField(max_length=30)
    type = models.CharField(max_length=100)
    niveau = models.CharField(max_length=100, blank=True)
    duree_annees = models.PositiveSmallIntegerField(default=3)
    nb_semestres = models.PositiveSmallIntegerField(default=6)
    credits_total = models.PositiveSmallIntegerField(default=180)
    responsable = models.ForeignKey(
        Utilisateur,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="formations_responsable",
    )
    accreditations = models.JSONField(default=list, blank=True)
    date_accreditation = models.DateField(null=True, blank=True)
    date_fin_accreditation = models.DateField(null=True, blank=True)
    regime = models.CharField(max_length=100, default="formation_initiale")
    description = models.TextField(blank=True)
    objectifs = models.TextField(blank=True)
    debouches = models.TextField(blank=True)
    conditions_admission = models.TextField(blank=True)
    actif = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("departement", "code")]
        verbose_name = "Formation"
        verbose_name_plural = "Formations"

    def __str__(self):
        return f"{self.code} - {self.nom}"

    def get_type_display(self):
        return dict(self.TYPE_CHOICES).get(self.type, self.type)

    def get_niveau_display(self):
        return dict(self.NIVEAU_CHOICES).get(self.niveau, self.niveau)

    def get_regime_display(self):
        return dict(self.REGIME_CHOICES).get(self.regime, self.regime)


class Parcours(models.Model):
    """Parcours au sein d'une formation (spécialisation)."""

    formation = models.ForeignKey(Formation, on_delete=models.CASCADE, related_name="parcours")
    nom = models.CharField(max_length=200)
    code = models.CharField(max_length=30)
    specialisation = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("formation", "code")]
        verbose_name = "Parcours"
        verbose_name_plural = "Parcours"

    def __str__(self):
        return f"{self.code} - {self.nom}"


class MaquetteFormation(models.Model):
    """Maquette pédagogique d'une formation pour une année."""

    formation = models.ForeignKey(Formation, on_delete=models.CASCADE, related_name="maquettes")
    annee_universitaire = models.ForeignKey(
        "etablissement.AnneeUniversitaire",
        on_delete=models.CASCADE,
        related_name="maquettes",
    )
    structure = models.JSONField(default=dict, help_text="Structure des UE par semestre")
    statut = models.CharField(
        max_length=20,
        choices=[
            ("brouillon", "Brouillon"),
            ("validee", "Validée"),
            ("archivee", "Archivée"),
        ],
        default="brouillon",
    )
    validee_par = models.ForeignKey(
        Utilisateur,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="maquettes_validees",
    )
    date_validation = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("formation", "annee_universitaire")]
        verbose_name = "Maquette de formation"
        verbose_name_plural = "Maquettes de formation"

    def __str__(self):
        return f"Maquette {self.formation} - {self.annee_universitaire}"
