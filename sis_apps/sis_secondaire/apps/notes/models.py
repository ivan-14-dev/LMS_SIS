"""Models for evaluations et notes (SIS Secondaire)."""

from apps.classes.models import Classe, Matiere
from apps.eleves.models import Eleve
from apps.enseignants.models import Personnel
from apps.etablissement.models import Periode
from django.db import models


class Evaluation(models.Model):
    """Évaluation (DS, interro, oral, etc.)."""

    TYPE_CHOICES = [
        ("interrogation", "Interrogation"),
        ("ds", "Devoir surveillé"),
        ("dm", "Devoir maison"),
        ("tp", "TP / Pratique"),
        ("oral", "Oral"),
        ("examen_blanc", "Examen blanc"),
        ("examen_final", "Examen final"),
        ("projet", "Projet"),
    ]
    matiere = models.ForeignKey(
        Matiere, on_delete=models.CASCADE, related_name="evaluations"
    )
    classe = models.ForeignKey(
        Classe, on_delete=models.CASCADE, related_name="evaluations"
    )
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="ds")
    titre = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    date = models.DateField()
    heure_debut = models.TimeField(null=True, blank=True)
    duree_minutes = models.PositiveIntegerField(null=True, blank=True)
    bareme = models.DecimalField(max_digits=5, decimal_places=2, default=20)
    coefficient = models.DecimalField(max_digits=4, decimal_places=2, default=1)
    periode = models.ForeignKey(
        Periode, on_delete=models.PROTECT, related_name="evaluations"
    )
    enseignant = models.ForeignKey(
        Personnel, on_delete=models.PROTECT, related_name="evaluations"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date"]
        indexes = [
            models.Index(fields=["classe", "date"]),
            models.Index(fields=["matiere", "date"]),
        ]

    def __str__(self):
        return f"{self.titre} - {self.classe}/{self.matiere}"


class Note(models.Model):
    """Note d'un élève à une évaluation."""

    STATUT_CHOICES = [
        ("presente", "Présentée"),
        ("absente", "Absent"),
        ("dispensee", "Dispensé"),
        ("non_rendue", "Non rendue"),
        ("triche", "Triche"),
    ]
    evaluation = models.ForeignKey(
        Evaluation, on_delete=models.CASCADE, related_name="notes"
    )
    eleve = models.ForeignKey(Eleve, on_delete=models.CASCADE, related_name="notes")
    valeur = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    appreciation = models.TextField(blank=True)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default="presente")
    date_saisie = models.DateTimeField(auto_now_add=True)
    saisi_par = models.ForeignKey(
        Personnel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notes_saisies",
    )
    modifie_le = models.DateTimeField(null=True, blank=True)
    modifie_par = models.ForeignKey(
        Personnel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notes_modifiees",
    )
    motif_modification = models.TextField(blank=True)

    class Meta:
        unique_together = [("evaluation", "eleve")]
        ordering = ["eleve__user__last_name", "eleve__user__first_name"]
        indexes = [
            models.Index(fields=["eleve", "evaluation"]),
        ]

    def __str__(self):
        return f"{self.eleve} - {self.evaluation} : {self.valeur}"


class Bulletin(models.Model):
    """Bulletin périodique d'un élève."""

    eleve = models.ForeignKey(Eleve, on_delete=models.CASCADE, related_name="bulletins")
    classe = models.ForeignKey(
        Classe, on_delete=models.PROTECT, related_name="bulletins"
    )
    periode = models.ForeignKey(
        Periode, on_delete=models.PROTECT, related_name="bulletins"
    )
    moyenne_generale = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    rang = models.PositiveIntegerField(null=True, blank=True)
    effectif_classe = models.PositiveIntegerField(null=True, blank=True)
    appreciation_conseil = models.TextField(blank=True)
    decision = models.CharField(
        max_length=50,
        blank=True,
        help_text="passage, redoublement, encouragement, etc.",
    )
    pdf_path = models.CharField(max_length=500, blank=True)
    signe = models.BooleanField(default=False)
    date_signature = models.DateTimeField(null=True, blank=True)
    publie = models.BooleanField(default=False)
    date_publication = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("eleve", "periode")]
        ordering = ["-periode__date_fin"]

    def __str__(self):
        return f"Bulletin {self.periode} - {self.eleve}"
