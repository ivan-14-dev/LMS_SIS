"""Models for recherche (SIS Supérieur)."""
from django.db import models
from apps.structure.models import Faculte, Departement
from apps.utilisateurs.models import Utilisateur
from apps.enseignants.models import EnseignantChercheur
from apps.etudiants.models import Etudiant


class Laboratoire(models.Model):
    """Laboratoire de recherche."""
    TYPE_CHOICES = [
        ("UMR", "Unité Mixte de Recherche"),
        ("EA", "Équipe d'Accueil"),
        ("FRE", "Formation de Recherche en Évolution"),
        ("USR", "Unité de Service et de Recherche"),
        ("individuel", "Laboratoire individuel"),
    ]
    faculte = models.ForeignKey(
        Faculte, on_delete=models.CASCADE, related_name="laboratoires",
        null=True, blank=True,
    )
    nom = models.CharField(max_length=200)
    acronyme = models.CharField(max_length=20)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="UMR")
    tutelle = models.JSONField(default=list, blank=True, help_text='["CNRS", "Université X"]')
    directeur = models.ForeignKey(
        EnseignantChercheur, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="laboratoires_diriges",
    )
    axes_recherche = models.JSONField(default=list, blank=True)
    numero_rnsr = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Laboratoire"
        verbose_name_plural = "Laboratoires"

    def __str__(self):
        return f"{self.acronyme} - {self.nom}"


class ProjetRecherche(models.Model):
    """Projet de recherche."""
    STATUT_CHOICES = [
        ("propose", "Proposé"),
        ("accepte", "Accepté"),
        ("en_cours", "En cours"),
        ("termine", "Terminé"),
        ("suspendu", "Suspendu"),
    ]
    laboratoire = models.ForeignKey(Laboratoire, on_delete=models.CASCADE, related_name="projets")
    titre = models.CharField(max_length=300)
    acronyme = models.CharField(max_length=20, blank=True)
    description = models.TextField()
    financeur = models.CharField(max_length=200, blank=True)
    reference = models.CharField(max_length=100, blank=True)
    budget = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    date_debut = models.DateField()
    date_fin = models.DateField()
    responsable = models.ForeignKey(
        EnseignantChercheur, on_delete=models.PROTECT, related_name="projets_responsable"
    )
    membres = models.ManyToManyField(EnseignantChercheur, related_name="projets_membre", blank=True)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default="propose")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Projet de recherche"
        verbose_name_plural = "Projets de recherche"

    def __str__(self):
        return self.titre


class ProductionScientifique(models.Model):
    """Article, communication, brevet, etc."""
    TYPE_CHOICES = [
        ("article", "Article scientifique"),
        ("communication", "Communication"),
        ("chapitre", "Chapitre d'ouvrage"),
        ("livre", "Livre"),
        ("brevet", "Brevet"),
        ("these", "Thèse"),
        ("hdr", "HDR"),
    ]
    projet = models.ForeignKey(
        ProjetRecherche, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="productions"
    )
    laboratoire = models.ForeignKey(
        Laboratoire, on_delete=models.CASCADE, related_name="productions"
    )
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    titre = models.CharField(max_length=300)
    auteurs = models.ManyToManyField(EnseignantChercheur, related_name="productions")
    annee = models.PositiveSmallIntegerField()
    doi = models.CharField(max_length=100, blank=True)
    fichier = models.FileField(upload_to="publications/", null=True, blank=True)
    url_hal = models.URLField(blank=True)
    facteur_impact = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Production scientifique"
        verbose_name_plural = "Productions scientifiques"

    def __str__(self):
        return f"{self.titre} ({self.annee})"


class These(models.Model):
    """Thèse de doctorat."""
    STATUT_CHOICES = [
        ("en_cours", "En cours"),
        ("soutenue", "Soutenue"),
        ("abandonnee", "Abandonnée"),
        ("suspendue", "Suspendue"),
    ]
    laboratoire = models.ForeignKey(Laboratoire, on_delete=models.CASCADE, related_name="theses")
    doctorant = models.OneToOneField(Etudiant, on_delete=models.CASCADE, related_name="these")
    directeur = models.ForeignKey(
        EnseignantChercheur, on_delete=models.PROTECT, related_name="theses_dirigees"
    )
    co_directeur = models.ForeignKey(
        EnseignantChercheur, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="theses_co_dirigees",
    )
    titre = models.CharField(max_length=300)
    resume = models.TextField()
    mots_cles = models.JSONField(default=list, blank=True)
    date_debut = models.DateField()
    date_soutenance = models.DateField(null=True, blank=True)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default="en_cours")
    financement = models.CharField(max_length=200, blank=True, help_text="Ex: MENRT, CIFRE, ANR")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Thèse"
        verbose_name_plural = "Thèses"

    def __str__(self):
        return f"{self.doctorant} - {self.titre[:60]}"
