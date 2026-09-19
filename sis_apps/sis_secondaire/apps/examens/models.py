"""Models for examens (SIS Secondaire)."""

from apps.classes.models import Classe, Matiere
from apps.eleves.models import Eleve
from apps.etablissement.models import AnneeScolaire
from apps.salles.models import Salle
from apps.utilisateurs.models import Utilisateur
from django.db import models


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

    epreuve = models.ForeignKey(
        EpreuveExamen, on_delete=models.CASCADE, related_name="resultats"
    )
    eleve = models.ForeignKey(
        Eleve, on_delete=models.CASCADE, related_name="resultats_examen"
    )
    note = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    appreciation = models.TextField(blank=True)
    numero_anonyme = models.CharField(max_length=20, blank=True)
    admis = models.BooleanField(default=False)
    mention = models.CharField(max_length=30, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("epreuve", "eleve")]
        verbose_name = "Résultat d'examen"
        verbose_name_plural = "Résultats d'examen"

    def __str__(self):
        return f"{self.eleve} - {self.epreuve} : {self.note}"
