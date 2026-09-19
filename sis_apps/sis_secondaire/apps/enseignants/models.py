"""Models for enseignants (SIS Secondaire)."""

from apps.classes.models import Classe, Matiere
from apps.utilisateurs.models import Utilisateur
from django.db import models


class Personnel(models.Model):
    """Personnel de l'établissement (enseignant, administratif)."""

    STATUT_CHOICES = [
        ("titulaire", "Titulaire"),
        ("contractuel", "Contractuel"),
        ("vacataire", "Vacataire"),
        ("stagiaire", "Stagiaire"),
    ]
    user = models.OneToOneField(
        Utilisateur, on_delete=models.CASCADE, related_name="personnel_profile"
    )
    matricule = models.CharField(max_length=50, unique=True)
    statut = models.CharField(
        max_length=20, choices=STATUT_CHOICES, default="titulaire"
    )
    date_embauche = models.DateField()
    corps = models.CharField(
        max_length=100, blank=True, help_text="Ex: Agrégé, Certifié"
    )
    diplomes = models.JSONField(default=list, blank=True)
    heures_contractuelles = models.DecimalField(
        max_digits=5, decimal_places=2, default=0
    )
    indice = models.PositiveIntegerField(null=True, blank=True)
    rib = models.CharField(max_length=50, blank=True)
    iban = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Personnel"
        verbose_name_plural = "Personnels"

    def __str__(self):
        return f"{self.matricule} - {self.user.get_full_name()}"


class MatiereEnseignee(models.Model):
    """Qualification : matière qu'un enseignant peut enseigner."""

    enseignant = models.ForeignKey(
        Personnel,
        on_delete=models.CASCADE,
        related_name="matieres_enseignees",
        limit_choices_to={"user__role": "enseignant"},
    )
    matiere = models.ForeignKey(
        Matiere, on_delete=models.CASCADE, related_name="enseignants_qualifies"
    )
    niveau_competence = models.PositiveSmallIntegerField(default=3, help_text="1 à 5")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("enseignant", "matiere")]
        verbose_name = "Matière enseignée"
        verbose_name_plural = "Matières enseignées"

    def __str__(self):
        return f"{self.enseignant} - {self.matiere}"


class AffectationEnseignant(models.Model):
    """Affectation d'un enseignant à une matière-classes pour une année."""

    enseignant = models.ForeignKey(
        Personnel,
        on_delete=models.CASCADE,
        related_name="affectations",
    )
    matiere = models.ForeignKey(
        Matiere, on_delete=models.CASCADE, related_name="affectations"
    )
    classes = models.ManyToManyField(Classe, related_name="affectations_enseignant")
    heures_semaine = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    annee_scolaire = models.ForeignKey(
        "etablissement.AnneeScolaire",
        on_delete=models.CASCADE,
        related_name="affectations_enseignant",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Affectation enseignant"
        verbose_name_plural = "Affectations enseignants"

    def __str__(self):
        return f"{self.enseignant} → {self.matiere}"
