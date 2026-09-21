"""Models for examens (SIS Secondaire)."""

import secrets

from apps.classes.models import Classe, Matiere
from apps.eleves.models import Eleve
from apps.etablissement.models import AnneeScolaire
from apps.salles.models import Salle
from apps.utilisateurs.models import Utilisateur
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from sis_common.exam_files import (
    PrivateExamStorage,
    exam_copy_upload_to,
    validate_exam_copy,
)


def generate_anonymous_number():
    return secrets.token_hex(10).upper()


class SessionExamen(models.Model):
    """Session d'examens (Brevet, Bac, examen blanc)."""

    TYPE_CHOICES = [
        ("bac", "Baccalauréat"),
        ("brevet", "Brevet des collèges"),
        ("examen_blanc", "Examen blanc"),
        ("controle", "Contrôle"),
        ("concours", "Concours"),
    ]
    annee_scolaire = models.ForeignKey(
        AnneeScolaire, on_delete=models.CASCADE, related_name="sessions_examens"
    )
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    nom = models.CharField(max_length=200)
    date_debut = models.DateField()
    date_fin = models.DateField()
    cloturee = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Session d'examen"
        verbose_name_plural = "Sessions d'examens"
        ordering = ["-date_debut"]

    def __str__(self):
        return f"{self.nom} - {self.date_debut}"


class EpreuveExamen(models.Model):
    """Épreuve d'examen (1 matière à 1 date)."""

    session = models.ForeignKey(
        SessionExamen, on_delete=models.CASCADE, related_name="epreuves"
    )
    matiere = models.ForeignKey(
        Matiere, on_delete=models.PROTECT, related_name="epreuves_examen"
    )
    classes = models.ManyToManyField(Classe, related_name="epreuves")
    date = models.DateField()
    heure_debut = models.TimeField()
    duree_minutes = models.PositiveIntegerField()
    debut_soumission = models.DateTimeField(null=True, blank=True)
    fin_soumission = models.DateTimeField(null=True, blank=True)
    salle_principale = models.ForeignKey(
        Salle,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="epreuves_principales",
    )
    bareme = models.DecimalField(max_digits=5, decimal_places=2, default=20)
    coefficient = models.DecimalField(max_digits=4, decimal_places=2, default=1)
    surveillants = models.ManyToManyField(
        Utilisateur, blank=True, related_name="surveillances_examen"
    )
    anonymat = models.BooleanField(default=True)
    nombre_corrections = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(2)],
        help_text="Une correction simple ou une double correction indépendante.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["date", "heure_debut"]
        indexes = [
            models.Index(fields=["session", "date"]),
        ]

    def __str__(self):
        return f"{self.session.nom} - {self.matiere} - {self.date}"


class ConvocationExamen(models.Model):
    """Convocation individuelle."""

    STATUT_CHOICES = [
        ("convoque", "Convoqué"),
        ("present", "Présent"),
        ("absent", "Absent"),
        ("dispense", "Dispensé"),
    ]
    epreuve = models.ForeignKey(
        EpreuveExamen, on_delete=models.CASCADE, related_name="convocations"
    )
    eleve = models.ForeignKey(
        Eleve, on_delete=models.CASCADE, related_name="convocations"
    )
    numero_place = models.CharField(max_length=10, blank=True)
    salle = models.CharField(max_length=100, blank=True)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default="convoque")
    notifie_parents = models.BooleanField(default=False)
    date_notification = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [("epreuve", "eleve")]
        verbose_name = "Convocation"
        verbose_name_plural = "Convocations"

    def __str__(self):
        return f"Convocation {self.eleve} - {self.epreuve}"


class ResultatExamen(models.Model):
    """Résultat d'un élève à une épreuve."""

    STATUT_CHOICES = [
        ("draft", "Brouillon"),
        ("submitted", "Soumis"),
        ("verified", "Vérifié"),
        ("validated", "Validé"),
        ("published", "Publié"),
        ("reopened", "Réouvert"),
        ("closed", "Clôturé"),
    ]
    TYPE_RESULTAT_CHOICES = [
        ("normal", "Ordinaire"),
        ("retake", "Rattrapage"),
    ]

    epreuve = models.ForeignKey(
        EpreuveExamen, on_delete=models.CASCADE, related_name="resultats"
    )
    eleve = models.ForeignKey(
        Eleve, on_delete=models.CASCADE, related_name="resultats_examen"
    )
    note = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    appreciation = models.TextField(blank=True)
    numero_anonyme = models.CharField(max_length=20, blank=True)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default="draft")
    type_resultat = models.CharField(
        max_length=20, choices=TYPE_RESULTAT_CHOICES, default="normal"
    )
    admis = models.BooleanField(default=False)
    mention = models.CharField(max_length=30, blank=True)
    saisi_par = models.ForeignKey(
        Utilisateur,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="resultats_examens_saisis",
    )
    saisi_le = models.DateTimeField(null=True, blank=True)
    verifie_par = models.ForeignKey(
        Utilisateur,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="resultats_examens_verifies",
    )
    verifie_le = models.DateTimeField(null=True, blank=True)
    valide_par = models.ForeignKey(
        Utilisateur,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="resultats_examens_valides",
    )
    valide_le = models.DateTimeField(null=True, blank=True)
    publie_par = models.ForeignKey(
        Utilisateur,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="resultats_examens_publies",
    )
    publie_le = models.DateTimeField(null=True, blank=True)
    reouvert_par = models.ForeignKey(
        Utilisateur,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="resultats_examens_reouverts",
    )
    reouvert_le = models.DateTimeField(null=True, blank=True)
    cloture_par = models.ForeignKey(
        Utilisateur,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="resultats_examens_clotures",
    )
    cloture_le = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        unique_together = [("epreuve", "eleve")]
        verbose_name = "Résultat d'examen"
        verbose_name_plural = "Résultats d'examen"
        indexes = [
            models.Index(fields=["statut", "type_resultat"]),
        ]

    def __str__(self):
        return f"{self.eleve} - {self.epreuve} : {self.note}"


class CopieExamen(models.Model):
    """Copie PDF privée, identifiée uniquement par un numéro anonyme."""

    STATUT_CHOICES = [
        ("deposee", "Déposée"),
        ("affectee", "Affectée"),
        ("correction", "En correction"),
        ("a_moderer", "À modérer"),
        ("finalisee", "Finalisée"),
    ]

    convocation = models.OneToOneField(
        ConvocationExamen, on_delete=models.PROTECT, related_name="copie"
    )
    numero_anonyme = models.CharField(
        max_length=20, unique=True, default=generate_anonymous_number, editable=False
    )
    fichier = models.FileField(
        upload_to=exam_copy_upload_to,
        storage=PrivateExamStorage(),
        validators=[validate_exam_copy],
    )
    empreinte_sha256 = models.CharField(max_length=64, editable=False)
    taille_octets = models.PositiveBigIntegerField(editable=False)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default="deposee")
    note_finale = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    moderee_par = models.ForeignKey(
        Utilisateur,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="copies_moderees",
    )
    moderee_le = models.DateTimeField(null=True, blank=True)
    motif_moderation = models.TextField(blank=True)
    deposee_par = models.ForeignKey(
        Utilisateur,
        on_delete=models.PROTECT,
        related_name="copies_examen_deposees",
    )
    deposee_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-deposee_le"]
        indexes = [
            models.Index(fields=["statut", "deposee_le"]),
            models.Index(fields=["convocation"]),
        ]

    def __str__(self):
        return self.numero_anonyme

    @property
    def epreuve(self):
        return self.convocation.epreuve


class AffectationCorrection(models.Model):
    """Affectation anonyme d'une copie à un correcteur."""

    STATUT_CHOICES = [
        ("assignee", "Assignée"),
        ("en_cours", "En cours"),
        ("soumise", "Soumise"),
    ]

    copie = models.ForeignKey(
        CopieExamen, on_delete=models.CASCADE, related_name="affectations"
    )
    correcteur = models.ForeignKey(
        Utilisateur, on_delete=models.PROTECT, related_name="corrections_assignees"
    )
    ordre = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(2)]
    )
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default="assignee")
    affectee_par = models.ForeignKey(
        Utilisateur, on_delete=models.PROTECT, related_name="affectations_correction"
    )
    affectee_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["copie", "ordre"], name="unique_ordre_correction_secondaire"
            ),
            models.UniqueConstraint(
                fields=["copie", "correcteur"],
                name="unique_correcteur_copie_secondaire",
            ),
        ]
        indexes = [models.Index(fields=["correcteur", "statut"])]

    def __str__(self):
        return f"{self.copie} - {self.correcteur} ({self.ordre})"


class CorrectionCopie(models.Model):
    """Note remise par un correcteur sans accès à l'identité de l'élève."""

    affectation = models.OneToOneField(
        AffectationCorrection, on_delete=models.CASCADE, related_name="correction"
    )
    note = models.DecimalField(max_digits=5, decimal_places=2)
    appreciation = models.TextField(blank=True)
    soumise_le = models.DateTimeField(auto_now_add=True)
    modifiee_le = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Correction de {self.affectation}"


class AuditCopieExamen(models.Model):
    """Journal append-only des opérations sensibles sur une copie."""

    copie = models.ForeignKey(
        CopieExamen, on_delete=models.PROTECT, related_name="audit"
    )
    acteur = models.ForeignKey(
        Utilisateur, on_delete=models.PROTECT, related_name="audit_copies_examen"
    )
    action = models.CharField(max_length=50)
    details = models.JSONField(default=dict, blank=True)
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-cree_le"]
        indexes = [models.Index(fields=["copie", "cree_le"])]

    def __str__(self):
        return f"{self.action} - {self.copie} ({self.cree_le})"
