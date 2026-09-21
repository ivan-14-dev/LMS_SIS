"""Models for evaluations et notes (SIS Secondaire)."""

from apps.classes.models import Classe, Matiere
from apps.eleves.models import Eleve
from apps.enseignants.models import Personnel
from apps.etablissement.models import Periode
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from sis_common.academic_configuration import evaluate_rule_criteria


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
    matiere = models.ForeignKey(Matiere, on_delete=models.CASCADE, related_name="evaluations")
    classe = models.ForeignKey(Classe, on_delete=models.CASCADE, related_name="evaluations")
    type = models.CharField(max_length=100, default="ds")
    titre = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    date = models.DateField()
    heure_debut = models.TimeField(null=True, blank=True)
    duree_minutes = models.PositiveIntegerField(null=True, blank=True)
    debut_soumission = models.DateTimeField(null=True, blank=True)
    fin_soumission = models.DateTimeField(null=True, blank=True)
    bareme = models.DecimalField(max_digits=5, decimal_places=2, default=20)
    coefficient = models.DecimalField(max_digits=4, decimal_places=2, default=1)
    ponderation = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=100,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Pourcentage de cette évaluation dans son regroupement.",
    )
    periode = models.ForeignKey(Periode, on_delete=models.PROTECT, related_name="evaluations")
    enseignant = models.ForeignKey(Personnel, on_delete=models.PROTECT, related_name="evaluations")
    eleve_cible = models.ForeignKey(
        Eleve,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="evaluations_individualisees",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date"]
        indexes = [
            models.Index(fields=["classe", "date"]),
            models.Index(fields=["matiere", "date"]),
            models.Index(fields=["eleve_cible", "date"]),
        ]

    def __str__(self):
        return f"{self.titre} - {self.classe}/{self.matiere}"

    def get_type_display(self):
        return dict(self.TYPE_CHOICES).get(self.type, self.type)


class Note(models.Model):
    """Note d'un élève à une évaluation."""

    STATUT_CHOICES = [
        ("presente", "Présentée"),
        ("absente", "Absent"),
        ("dispensee", "Dispensé"),
        ("non_rendue", "Non rendue"),
        ("triche", "Triche"),
    ]
    evaluation = models.ForeignKey(Evaluation, on_delete=models.CASCADE, related_name="notes")
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
    classe = models.ForeignKey(Classe, on_delete=models.PROTECT, related_name="bulletins")
    periode = models.ForeignKey(Periode, on_delete=models.PROTECT, related_name="bulletins")
    moyenne_generale = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
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


class RegleValidation(models.Model):
    """Règle de passage configurable pour une année, un niveau ou une classe."""

    code = models.SlugField(max_length=60)
    libelle = models.CharField(max_length=160)
    annee_scolaire = models.ForeignKey(
        "etablissement.AnneeScolaire",
        on_delete=models.CASCADE,
        related_name="regles_validation",
    )
    niveau = models.ForeignKey(
        "etablissement.Niveau",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="regles_validation",
    )
    classe = models.ForeignKey(
        "classes.Classe",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="regles_validation",
    )
    seuil_moyenne = models.DecimalField(max_digits=5, decimal_places=2, default=10)
    note_eliminatoire = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    credits_minimum = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    max_matieres_echouees = models.PositiveSmallIntegerField(null=True, blank=True)
    compensation_autorisee = models.BooleanField(default=True)
    criteres = models.JSONField(default=dict, blank=True)
    priorite = models.PositiveSmallIntegerField(default=100)
    actif = models.BooleanField(default=True)

    class Meta:
        ordering = ["priorite", "code"]
        constraints = [
            models.UniqueConstraint(
                fields=["annee_scolaire", "code"],
                name="unique_regle_validation_secondaire",
            )
        ]

    def __str__(self):
        return f"{self.code} - {self.libelle}"

    def evaluer(
        self,
        moyenne,
        credits=0,
        matieres_echouees=0,
        note_minimale=None,
        donnees=None,
        policy=None,
    ):
        donnees = donnees or {}
        thresholds = (policy or {}).get("thresholds", {})
        publication = (policy or {}).get("publication", {})
        seuil_moyenne = thresholds.get("seuil_moyenne", self.seuil_moyenne)
        credits_minimum = thresholds.get("credits_minimum", self.credits_minimum)
        max_matieres_echouees = thresholds.get("max_matieres_echouees", self.max_matieres_echouees)
        note_eliminatoire = thresholds.get("note_eliminatoire", self.note_eliminatoire)
        criteres = {**self.criteres, **(policy or {}).get("criteria", {})}
        motifs = []
        if moyenne < seuil_moyenne:
            motifs.append("moyenne_insuffisante")
        if credits < credits_minimum:
            motifs.append("credits_insuffisants")
        if max_matieres_echouees is not None and matieres_echouees > max_matieres_echouees:
            motifs.append("trop_de_matieres_echouees")
        if note_eliminatoire is not None and note_minimale is not None and note_minimale < note_eliminatoire:
            motifs.append("note_eliminatoire")
        motifs.extend(evaluate_rule_criteria(criteres, donnees))
        if publication.get("requires_financial_clearance") and not donnees.get("financial_clearance", False):
            motifs.append("financial_clearance_required")
        return {"reussi": not motifs, "motifs": motifs}
