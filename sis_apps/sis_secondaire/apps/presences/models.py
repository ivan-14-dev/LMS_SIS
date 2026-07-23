"""Models for presences (SIS Secondaire)."""
from django.db import models
from apps.eleves.models import Eleve
from apps.emplois_du_temps.models import Creneau
from apps.enseignants.models import Personnel


class Appel(models.Model):
    """Appel fait par un enseignant pour un créneau donné."""
    creneau = models.ForeignKey(Creneau, on_delete=models.CASCADE, related_name="appels")
    date = models.DateField()
    enseignant = models.ForeignKey(
        Personnel, on_delete=models.PROTECT, related_name="appels"
    )
    statut = models.CharField(
        max_length=20,
        choices=[("ouvert", "Ouvert"), ("ferme", "Fermé"), ("valide", "Validé")],
        default="ouvert",
    )
    date_saisie = models.DateTimeField(auto_now_add=True)
    date_validation = models.DateTimeField(null=True, blank=True)
    commentaire_global = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("creneau", "date")]
        ordering = ["-date", "-creneau__heure_debut"]

    def __str__(self):
        return f"Appel {self.creneau} - {self.date}"


class Presence(models.Model):
    """Présence individuelle d'un élève à un appel."""
    STATUT_CHOICES = [
        ("present", "Présent"),
        ("absent", "Absent"),
        ("absent_justifie", "Absent justifié"),
        ("retard", "Retard"),
        ("sortie_anticipee", "Sortie anticipée"),
        ("dispense", "Dispensé"),
    ]
    appel = models.ForeignKey(Appel, on_delete=models.CASCADE, related_name="presences")
    eleve = models.ForeignKey(Eleve, on_delete=models.CASCADE, related_name="presences")
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default="present")
    retard_minutes = models.PositiveSmallIntegerField(null=True, blank=True)
    sortie_heure = models.TimeField(null=True, blank=True)
    commentaire = models.TextField(blank=True)
    notifie_parent = models.BooleanField(default=False)
    date_notification = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [("appel", "eleve")]
        indexes = [
            models.Index(fields=["eleve", "appel"]),
        ]

    def __str__(self):
        return f"{self.eleve} - {self.appel} : {self.get_statut_display()}"


class Justificatif(models.Model):
    """Justificatif d'absence."""
    STATUT_CHOICES = [
        ("en_attente", "En attente"),
        ("accepte", "Accepté"),
        ("refuse", "Refusé"),
    ]
    presence = models.OneToOneField(
        Presence, on_delete=models.CASCADE, related_name="justificatif"
    )
    motif = models.TextField()
    document = models.FileField(upload_to="justificatifs/", null=True, blank=True)
    date_depot = models.DateTimeField(auto_now_add=True)
    valide_par = models.ForeignKey(
        Personnel, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="justificatifs_valides",
    )
    date_validation = models.DateTimeField(null=True, blank=True)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default="en_attente")
    commentaire_validation = models.TextField(blank=True)

    def __str__(self):
        return f"Justificatif {self.presence} - {self.get_statut_display()}"
