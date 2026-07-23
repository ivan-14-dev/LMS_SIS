"""Models for discipline (SIS Secondaire)."""
from django.db import models
from apps.eleves.models import Eleve
from apps.enseignants.models import Personnel


class Incident(models.Model):
    """Incident disciplinaire."""
    TYPE_CHOICES = [
        ("comportement", "Comportement"),
        ("violence", "Violence"),
        ("deffaillance", "Défaillance travail"),
        ("fraude", "Fraude / Triche"),
        ("manquement_respect", "Manquement respect"),
        ("degradation", "Dégradation"),
        ("autre", "Autre"),
    ]
    GRAVITE_CHOICES = [
        (1, "Mineur"),
        (2, "Modéré"),
        (3, "Grave"),
        (4, "Très grave"),
    ]
    STATUT_CHOICES = [
        ("ouvert", "Ouvert"),
        ("en_instruction", "En instruction"),
        ("sanctionne", "Sanctionné"),
        ("classe", "Classé sans suite"),
    ]
    eleve = models.ForeignKey(Eleve, on_delete=models.CASCADE, related_name="incidents")
    date_incident = models.DateTimeField()
    type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    gravite = models.PositiveSmallIntegerField(choices=GRAVITE_CHOICES, default=1)
    description = models.TextField()
    lieu = models.CharField(max_length=200, blank=True)
    temoins = models.ManyToManyField(Personnel, blank=True, related_name="incidents_temoins")
    rapporteur = models.ForeignKey(
        Personnel, on_delete=models.PROTECT, related_name="incidents_rapportes"
    )
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default="ouvert")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date_incident"]
        indexes = [
            models.Index(fields=["eleve", "date_incident"]),
        ]

    def __str__(self):
        return f"Incident {self.eleve} - {self.date_incident}"


class Sanction(models.Model):
    """Sanction décidée suite à un incident."""
    TYPE_CHOICES = [
        ("avertissement", "Avertissement"),
        ("heures_colle", "Heures de colle"),
        ("exclusion_cours", "Exclusion de cours"),
        ("exclusion_temporaire", "Exclusion temporaire"),
        ("exclusion_definitive", "Exclusion définitive"),
        ("travail_interet_general", "Travail d'intérêt général"),
        ("autre", "Autre"),
    ]
    incident = models.ForeignKey(Incident, on_delete=models.CASCADE, related_name="sanctions")
    type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    duree_jours = models.PositiveSmallIntegerField(null=True, blank=True)
    date_effet = models.DateField()
    date_fin = models.DateField(null=True, blank=True)
    motif = models.TextField()
    notifiee_parents = models.BooleanField(default=False)
    date_notification = models.DateTimeField(null=True, blank=True)
    executee = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_effet"]

    def __str__(self):
        return f"{self.get_type_display()} - {self.incident.eleve}"


class ConseilDiscipline(models.Model):
    """Conseil de discipline."""
    STATUT_CHOICES = [
        ("planifie", "Planifié"),
        ("tenu", "Tenu"),
        ("annule", "Annulé"),
    ]
    eleve = models.ForeignKey(Eleve, on_delete=models.CASCADE, related_name="conseils_discipline")
    date = models.DateTimeField()
    president = models.ForeignKey(
        Personnel, on_delete=models.PROTECT, related_name="conseils_presides"
    )
    membres = models.ManyToManyField(Personnel, related_name="conseils_membre")
    incidents = models.ManyToManyField(Incident, related_name="conseils")
    sanction = models.ForeignKey(
        Sanction, on_delete=models.SET_NULL, null=True, blank=True, related_name="conseils"
    )
    pv = models.TextField(blank=True)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default="planifie")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"Conseil de discipline - {self.eleve} - {self.date}"
