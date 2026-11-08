"""Models for salles (SIS Secondaire)."""

from apps.etablissement.models import Etablissement
from django.db import models

from sis_common.event_occupancy import EventOccupancyGuard


class Salle(EventOccupancyGuard, models.Model):
    """Salle de classe / laboratoire / gymnase."""

    TYPE_CHOICES = [
        ("salle_classique", "Salle de classe"),
        ("laboratoire", "Laboratoire"),
        ("salle_info", "Salle informatique"),
        ("gymnase", "Gymnase"),
        ("amphi", "Amphithéâtre"),
        ("bibliotheque", "Bibliothèque"),
        ("cdi", "CDI"),
        ("reunion", "Salle de réunion"),
    ]
    etablissement = models.ForeignKey(
        Etablissement, on_delete=models.CASCADE, related_name="salles"
    )
    nom = models.CharField(max_length=100)
    code = models.CharField(max_length=20)
    batiment = models.CharField(max_length=100, blank=True)
    etage = models.CharField(max_length=20, blank=True)
    capacite = models.PositiveIntegerField(default=30)
    type = models.CharField(
        max_length=30, choices=TYPE_CHOICES, default="salle_classique"
    )
    equipements = models.JSONField(
        default=list, blank=True, help_text='["projecteur", "tableau_interactif"]'
    )
    accessible_pm = models.BooleanField(
        default=True, help_text="Accessible personne mobilité réduite"
    )
    surface_m2 = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("etablissement", "code")]
        ordering = ["batiment", "nom"]

    def __str__(self):
        return f"{self.nom} ({self.batiment})"


class Equipement(models.Model):
    """Équipement inventorié ; seuls les équipements actifs peuvent être affectés."""

    etablissement = models.ForeignKey(
        Etablissement, on_delete=models.CASCADE, related_name="equipements_salles"
    )
    identifiant = models.CharField(max_length=50)
    nom = models.CharField(max_length=100)
    actif = models.BooleanField(default=True)
    salle = models.ForeignKey(
        Salle, on_delete=models.SET_NULL, null=True, blank=True, related_name="materiel"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["identifiant"]
        constraints = [
            models.UniqueConstraint(
                fields=["etablissement", "identifiant"],
                name="salles_equipement_identifiant_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(actif=True) | models.Q(salle__isnull=True),
                name="salles_equipement_inactif_sans_salle",
            ),
        ]

    def __str__(self):
        return f"{self.identifiant} — {self.nom}"


class IndisponibiliteSalle(EventOccupancyGuard, models.Model):
    """Période de jours entiers pendant laquelle une salle ne peut être planifiée."""

    salle = models.ForeignKey(
        Salle, on_delete=models.CASCADE, related_name="indisponibilites"
    )
    date_debut = models.DateField()
    date_fin = models.DateField()
    motif = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["date_debut", "id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(date_fin__gte=models.F("date_debut")),
                name="salles_indisponibilite_dates_valides",
            )
        ]
        indexes = [
            models.Index(
                fields=["salle", "date_debut", "date_fin"],
                name="salles_indisp_dates_idx",
            )
        ]
