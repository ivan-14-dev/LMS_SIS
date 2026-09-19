"""Models for examens (SIS Supérieur)."""

from apps.etablissement.models import Semestre
from apps.ue_ecue.models import ECUE
from apps.utilisateurs.models import Utilisateur
from django.db import models


class SessionExamen(models.Model):
    """Session d'examens (session 1, session 2 rattrapage)."""

    NUMERO_CHOICES = [(1, "Session 1 (normale)"), (2, "Session 2 (rattrapage)")]
    TYPE_CHOICES = [
        ("normale", "Normale"),
        ("rattrapage", "Rattrapage"),
        ("exceptionnelle", "Exceptionnelle"),
    ]
    semestre = models.ForeignKey(
        Semestre, on_delete=models.CASCADE, related_name="sessions_examens"
    )
    numero = models.PositiveSmallIntegerField(choices=NUMERO_CHOICES)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="normale")
    date_debut = models.DateField()
    date_fin = models.DateField()
    cloturee = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("semestre", "numero")]
        ordering = ["semestre", "numero"]

    def __str__(self):
        return f"Session {self.numero} - {self.semestre}"


class EpreuveExamen(models.Model):
    """Épreuve d'examen (1 épreuve = 1 ECUE à 1 date)."""

    session = models.ForeignKey(
        SessionExamen, on_delete=models.CASCADE, related_name="epreuves"
    )
    ecue = models.ForeignKey(ECUE, on_delete=models.CASCADE, related_name="epreuves")
    date = models.DateField()
    heure_debut = models.TimeField()
    duree_minutes = models.PositiveIntegerField()
    lieu = models.CharField(max_length=200, help_text="Bâtiment / amphithéâtre")
    places_totales = models.PositiveIntegerField(default=0)
    surveillants = models.ManyToManyField(
        Utilisateur,
        blank=True,
        related_name="surveillances",
        limit_choices_to={"role__in": ["enseignant", "personnel_administratif"]},
    )
    anonymat = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["date", "heure_debut"]
        indexes = [
            models.Index(fields=["session", "date"]),
        ]

    def __str__(self):
        return f"{self.ecue} - {self.date} {self.heure_debut}"


class ConvocationExamen(models.Model):
    """Convocation d'un étudiant à une épreuve."""

    STATUT_CHOICES = [
        ("convoque", "Convoqué"),
        ("present", "Présent"),
        ("absent", "Absent"),
        ("dispense", "Dispensé"),
        ("annule", "Annulé"),
    ]
    epreuve = models.ForeignKey(
        EpreuveExamen, on_delete=models.CASCADE, related_name="convocations"
    )
    etudiant = models.ForeignKey(
        "etudiants.Etudiant", on_delete=models.CASCADE, related_name="convocations"
    )
    numero_place = models.CharField(max_length=10, blank=True)
    salle = models.CharField(max_length=100, blank=True)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default="convoque")
    notifie = models.BooleanField(default=False)
    date_notification = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [("epreuve", "etudiant")]
        verbose_name = "Convocation examen"
        verbose_name_plural = "Convocations examen"

    def __str__(self):
        return f"Convocation {self.etudiant} - {self.epreuve}"
