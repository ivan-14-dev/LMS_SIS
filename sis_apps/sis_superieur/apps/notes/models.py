"""Models for notes (SIS Supérieur)."""

from apps.etablissement.models import Semestre
from apps.etudiants.models import Etudiant
from apps.ue_ecue.models import ECUE, UE
from apps.utilisateurs.models import Utilisateur
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from sis_common.academic_configuration import evaluate_rule_criteria


class Evaluation(models.Model):
    """Évaluation (CC, examen, oral, etc.)."""

    MODALITE_CHOICES = [
        ("cc", "Contrôle continu"),
        ("examen_ecrit", "Examen écrit"),
        ("examen_oral", "Examen oral"),
        ("tp", "TP / Pratique"),
        ("projet", "Projet"),
        ("rattrapage", "Rattrapage"),
    ]
    ecue = models.ForeignKey(ECUE, on_delete=models.CASCADE, related_name="evaluations")
    type = models.CharField(max_length=20, default="cc")
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
    modalite = models.CharField(max_length=100, default="cc")
    semestre = models.ForeignKey(Semestre, on_delete=models.PROTECT, related_name="evaluations")
    enseignant = models.ForeignKey(
        Utilisateur,
        on_delete=models.PROTECT,
        related_name="evaluations_creees",
        limit_choices_to={"role__in": ["enseignant", "chercheur"]},
    )
    anonyme = models.BooleanField(default=False, help_text="Notation anonyme")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date"]
        indexes = [
            models.Index(fields=["ecue", "date"]),
        ]

    def __str__(self):
        return f"{self.titre} - {self.ecue}"

    def get_modalite_display(self):
        return dict(self.MODALITE_CHOICES).get(self.modalite, self.modalite)


class Note(models.Model):
    """Note d'un étudiant à une évaluation."""

    STATUT_CHOICES = [
        ("presente", "Présentée"),
        ("absente", "Absent"),
        ("absent_justifie", "Absent justifié"),
        ("dispense", "Dispensé"),
        ("non_rendue", "Non rendue"),
        ("triche", "Triche"),
        ("en_attente", "En attente"),
    ]
    evaluation = models.ForeignKey(Evaluation, on_delete=models.CASCADE, related_name="notes")
    etudiant = models.ForeignKey(Etudiant, on_delete=models.CASCADE, related_name="notes")
    valeur = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    numero_anonyme = models.CharField(max_length=20, blank=True)
    appreciation = models.TextField(blank=True)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default="en_attente")
    date_saisie = models.DateTimeField(auto_now_add=True)
    saisi_par = models.ForeignKey(
        Utilisateur,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notes_saisies_u",
    )
    modifie_le = models.DateTimeField(null=True, blank=True)
    modifie_par = models.ForeignKey(
        Utilisateur,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notes_modifiees_u",
    )
    motif_modification = models.TextField(blank=True)

    class Meta:
        unique_together = [("evaluation", "etudiant")]
        ordering = ["etudiant__user__last_name"]

    def __str__(self):
        return f"{self.etudiant} - {self.evaluation} : {self.valeur}"


class MoyenneECUE(models.Model):
    """Moyenne calculée pour un ECUE / étudiant."""

    etudiant = models.ForeignKey(Etudiant, on_delete=models.CASCADE, related_name="moyennes_ecue")
    ecue = models.ForeignKey(ECUE, on_delete=models.CASCADE, related_name="moyennes")
    semestre = models.ForeignKey(Semestre, on_delete=models.CASCADE, related_name="moyennes_ecue")
    moyenne = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    valide = models.BooleanField(default=False)
    date_calcul = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("etudiant", "ecue", "semestre")]

    def __str__(self):
        return f"{self.etudiant} - {self.ecue} : {self.moyenne}"


class MoyenneUE(models.Model):
    """Moyenne calculée pour une UE / étudiant."""

    etudiant = models.ForeignKey(Etudiant, on_delete=models.CASCADE, related_name="moyennes_ue")
    ue = models.ForeignKey(UE, on_delete=models.CASCADE, related_name="moyennes")
    semestre = models.ForeignKey(Semestre, on_delete=models.CASCADE, related_name="moyennes_ue")
    moyenne = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    credits_obtenus = models.DecimalField(max_digits=4, decimal_places=2, default=0)
    capitalisee = models.BooleanField(default=False)
    date_calcul = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("etudiant", "ue", "semestre")]

    def __str__(self):
        return f"{self.etudiant} - {self.ue} : {self.moyenne}"


class RegleValidation(models.Model):
    """Règle de réussite configurable par formation et semestre."""

    code = models.SlugField(max_length=60)
    libelle = models.CharField(max_length=160)
    annee_universitaire = models.ForeignKey(
        "etablissement.AnneeUniversitaire",
        on_delete=models.CASCADE,
        related_name="regles_validation",
    )
    formation = models.ForeignKey(
        "formations.Formation",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="regles_validation",
    )
    semestre = models.ForeignKey(
        "etablissement.Semestre",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="regles_validation",
    )
    seuil_moyenne = models.DecimalField(max_digits=5, decimal_places=2, default=10)
    note_eliminatoire = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    credits_minimum = models.DecimalField(max_digits=7, decimal_places=2, default=30)
    max_ecues_echoues = models.PositiveSmallIntegerField(null=True, blank=True)
    compensation_autorisee = models.BooleanField(default=True)
    criteres = models.JSONField(default=dict, blank=True)
    priorite = models.PositiveSmallIntegerField(default=100)
    actif = models.BooleanField(default=True)

    class Meta:
        ordering = ["priorite", "code"]
        constraints = [
            models.UniqueConstraint(
                fields=["annee_universitaire", "code"],
                name="unique_regle_validation_superieur",
            )
        ]

    def evaluer(
        self,
        moyenne,
        credits=0,
        ecues_echoues=0,
        note_minimale=None,
        donnees=None,
        policy=None,
    ):
        donnees = donnees or {}
        thresholds = (policy or {}).get("thresholds", {})
        publication = (policy or {}).get("publication", {})
        seuil_moyenne = thresholds.get("seuil_moyenne", self.seuil_moyenne)
        credits_minimum = thresholds.get("credits_minimum", self.credits_minimum)
        max_ecues_echoues = thresholds.get("max_ecues_echoues", self.max_ecues_echoues)
        note_eliminatoire = thresholds.get("note_eliminatoire", self.note_eliminatoire)
        criteres = {**self.criteres, **(policy or {}).get("criteria", {})}
        motifs = []
        if moyenne < seuil_moyenne:
            motifs.append("moyenne_insuffisante")
        if credits < credits_minimum:
            motifs.append("credits_insuffisants")
        if max_ecues_echoues is not None and ecues_echoues > max_ecues_echoues:
            motifs.append("trop_ecues_echoues")
        if note_eliminatoire is not None and note_minimale is not None and note_minimale < note_eliminatoire:
            motifs.append("note_eliminatoire")
        motifs.extend(evaluate_rule_criteria(criteres, donnees))
        if publication.get("requires_financial_clearance") and not donnees.get("financial_clearance", False):
            motifs.append("financial_clearance_required")
        return {"reussi": not motifs, "motifs": motifs}
