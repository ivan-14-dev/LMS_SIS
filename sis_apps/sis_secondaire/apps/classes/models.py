"""Models for classes (SIS Secondaire)."""

from apps.etablissement.models import AnneeScolaire, Etablissement, Niveau
from apps.utilisateurs.models import Utilisateur
from django.db import models


class Classe(models.Model):
    """Classe d'un établissement (ex: 6e A, Terminale C)."""

    etablissement = models.ForeignKey(
        Etablissement,
        on_delete=models.CASCADE,
        related_name="classes",
        null=True,
        blank=True,
    )
    annee_scolaire = models.ForeignKey(AnneeScolaire, on_delete=models.CASCADE, related_name="classes")
    niveau = models.ForeignKey(Niveau, on_delete=models.PROTECT, related_name="classes")
    nom = models.CharField(max_length=50, help_text="Ex: 6e A, Terminale C")
    effectif_max = models.PositiveIntegerField(default=40)
    salle_principale = models.ForeignKey(
        "salles.Salle",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="classes_principales",
    )
    prof_principal = models.ForeignKey(
        Utilisateur,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="classes_principales",
        limit_choices_to={"role": "enseignant"},
    )
    color = models.CharField(max_length=7, default="#3B82F6", help_text="Code couleur")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("annee_scolaire", "nom")]
        ordering = ["niveau__ordre", "nom"]

    def __str__(self):
        return f"{self.nom} ({self.annee_scolaire.libelle})"

    @property
    def effectif_actuel(self):
        return self.eleves_actuels.count()


class Groupe(models.Model):
    """Sous-groupe d'élèves (TD, TP, options, langue)."""

    TYPE_CHOICES = [
        ("langue", "Langue"),
        ("option", "Option"),
        ("td", "TD"),
        ("tp", "TP"),
        ("soutien", "Soutien"),
        ("approfondissement", "Approfondissement"),
    ]
    etablissement = models.ForeignKey(
        Etablissement,
        on_delete=models.CASCADE,
        related_name="groupes",
        null=True,
        blank=True,
    )
    annee_scolaire = models.ForeignKey(AnneeScolaire, on_delete=models.CASCADE, related_name="groupes")
    classes = models.ManyToManyField(Classe, related_name="groupes")
    nom = models.CharField(max_length=100)
    type = models.CharField(max_length=100)
    capacite = models.PositiveIntegerField(default=30)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Groupe"
        verbose_name_plural = "Groupes"

    def __str__(self):
        return f"{self.nom} ({self.get_type_display()})"

    def get_type_display(self):
        return dict(self.TYPE_CHOICES).get(self.type, self.type)


class Matiere(models.Model):
    """Matière enseignée (math, français...)."""

    TYPE_CHOICES = [
        ("fondamentale", "Fondamentale"),
        ("optionnelle", "Optionnelle"),
        ("transversale", "Transversale"),
        ("eps", "EPS"),
        ("langues", "Langues"),
    ]
    etablissement = models.ForeignKey(
        Etablissement,
        on_delete=models.CASCADE,
        related_name="matieres",
        null=True,
        blank=True,
    )
    code = models.CharField(max_length=20)
    nom = models.CharField(max_length=100)
    type = models.CharField(max_length=100, default="fondamentale")
    couleur = models.CharField(max_length=7, default="#10B981")
    coefficient_defaut = models.DecimalField(max_digits=4, decimal_places=2, default=1)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("etablissement", "code")]
        ordering = ["nom"]

    def __str__(self):
        return self.nom

    def get_type_display(self):
        return dict(self.TYPE_CHOICES).get(self.type, self.type)


class ProgrammeMatiere(models.Model):
    """Affectation d'une matière à une classe avec coefficient et horaires."""

    classe = models.ForeignKey(Classe, on_delete=models.CASCADE, related_name="programmes")
    matiere = models.ForeignKey(Matiere, on_delete=models.CASCADE, related_name="programmes")
    coefficient = models.DecimalField(max_digits=4, decimal_places=2, default=1)
    credits = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    heures_semaine = models.DecimalField(max_digits=4, decimal_places=2, default=0)
    obligatoire = models.BooleanField(default=True)
    enseignant_principal = models.ForeignKey(
        Utilisateur,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="programmes_principaux",
        limit_choices_to={"role": "enseignant"},
    )
    enseignants = models.ManyToManyField(
        Utilisateur,
        blank=True,
        related_name="programmes_enseignes",
        limit_choices_to={"role": "enseignant"},
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("classe", "matiere")]
        verbose_name = "Programme de matière"
        verbose_name_plural = "Programmes de matières"

    def __str__(self):
        return f"{self.classe} - {self.matiere} (coeff {self.coefficient})"


class Chapitre(models.Model):
    """Chapitre d'un programme d'enseignement."""

    matiere = models.ForeignKey(Matiere, on_delete=models.CASCADE, related_name="chapitres")
    niveau = models.ForeignKey(Niveau, on_delete=models.CASCADE, related_name="chapitres")
    ordre = models.PositiveIntegerField()
    titre = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    objectifs = models.TextField(blank=True)
    progression = models.PositiveIntegerField(default=0, help_text="% progression")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("matiere", "niveau", "ordre")]
        ordering = ["matiere", "niveau", "ordre"]

    def __str__(self):
        return f"{self.matiere} - {self.titre}"
