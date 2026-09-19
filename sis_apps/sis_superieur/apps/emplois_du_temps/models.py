"""Models for emplois du temps (SIS Supérieur)."""

from apps.enseignants.models import EnseignantChercheur
from apps.etablissement.models import Semestre
from apps.formations.models import Formation
from apps.structure.models import Departement
from apps.ue_ecue.models import ECUE
from apps.utilisateurs.models import Utilisateur
from django.db import models


class Batiment(models.Model):
    """Bâtiment du campus."""

    nom = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)
    adresse = models.TextField(blank=True)
    nb_etages = models.PositiveSmallIntegerField(default=1)
    accessibilite_pmr = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Bâtiment"
        verbose_name_plural = "Bâtiments"
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} - {self.nom}"


class Salle(models.Model):
    """Salle de cours ou de réunion."""

    TYPE_CHOICES = [
        ("amphi", "Amphithéâtre"),
        ("td", "Salle de TD"),
        ("tp", "Salle de TP"),
        ("info", "Salle informatique"),
        ("labo", "Laboratoire"),
        ("reunion", "Salle de réunion"),
        ("visio", "Salle de visioconférence"),
        ("autre", "Autre"),
    ]
    batiment = models.ForeignKey(
        Batiment, on_delete=models.CASCADE, related_name="salles"
    )
    nom = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="td")
    capacite = models.PositiveIntegerField()
    etage = models.SmallIntegerField(default=0)
    equipements = models.JSONField(
        default=list, blank=True, help_text='["vidéoprojecteur", "tableau blanc", ...]'
    )
    accessibilite_pmr = models.BooleanField(default=False)
    disponible = models.BooleanField(default=True)
    departement_gestionnaire = models.ForeignKey(
        Departement,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="salles_gerees",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Salle"
        verbose_name_plural = "Salles"
        ordering = ["batiment", "code"]

    def __str__(self):
        return f"{self.code} ({self.batiment.code})"


class CreneauHoraire(models.Model):
    """Créneau horaire type (ex: 8h-10h)."""

    heure_debut = models.TimeField()
    heure_fin = models.TimeField()
    libelle = models.CharField(max_length=50, blank=True)
    ordre = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "Créneau horaire"
        verbose_name_plural = "Créneaux horaires"
        ordering = ["ordre", "heure_debut"]
        unique_together = [("heure_debut", "heure_fin")]

    def __str__(self):
        return (
            self.libelle
            or f"{self.heure_debut.strftime('%H:%M')}-{self.heure_fin.strftime('%H:%M')}"
        )


class CreneauCours(models.Model):
    """Créneau de cours dans l'emploi du temps."""

    JOUR_CHOICES = [
        (0, "Lundi"),
        (1, "Mardi"),
        (2, "Mercredi"),
        (3, "Jeudi"),
        (4, "Vendredi"),
        (5, "Samedi"),
        (6, "Dimanche"),
    ]
    TYPE_CHOICES = [
        ("CM", "Cours magistral"),
        ("TD", "Travaux dirigés"),
        ("TP", "Travaux pratiques"),
        ("projet", "Projet"),
        ("examen", "Examen"),
        ("autre", "Autre"),
    ]
    semestre = models.ForeignKey(
        Semestre, on_delete=models.CASCADE, related_name="creneaux_cours"
    )
    formation = models.ForeignKey(
        Formation, on_delete=models.CASCADE, related_name="creneaux_cours"
    )
    ecue = models.ForeignKey(ECUE, on_delete=models.CASCADE, related_name="creneaux")
    enseignant = models.ForeignKey(
        EnseignantChercheur,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="creneaux_cours",
    )
    salle = models.ForeignKey(
        Salle,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="creneaux_cours",
    )
    jour = models.SmallIntegerField(choices=JOUR_CHOICES)
    creneau_horaire = models.ForeignKey(
        CreneauHoraire, on_delete=models.PROTECT, related_name="creneaux_cours"
    )
    type_cours = models.CharField(max_length=20, choices=TYPE_CHOICES, default="CM")
    groupe = models.CharField(max_length=20, blank=True, help_text="Ex: Groupe A, TD1")
    semaine_debut = models.PositiveSmallIntegerField(default=1)
    semaine_fin = models.PositiveSmallIntegerField(default=52)
    frequence = models.CharField(
        max_length=20,
        default="hebdomadaire",
        choices=[
            ("hebdomadaire", "Hebdomadaire"),
            ("bihebdomadaire", "Toutes les 2 semaines"),
            ("mensuel", "Mensuel"),
        ],
    )
    semaines_paires = models.BooleanField(
        null=True,
        blank=True,
        help_text="True=semaines paires, False=impaires, None=toutes",
    )
    commentaire = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Créneau de cours"
        verbose_name_plural = "Créneaux de cours"
        ordering = ["jour", "creneau_horaire__ordre"]

    def __str__(self):
        return f"{self.ecue.code} - {self.get_jour_display()} {self.creneau_horaire}"


class Reservation(models.Model):
    """Réservation ponctuelle d'une salle."""

    STATUT_CHOICES = [
        ("en_attente", "En attente"),
        ("confirmee", "Confirmée"),
        ("refusee", "Refusée"),
        ("annulee", "Annulée"),
    ]
    MOTIF_CHOICES = [
        ("cours_rattrapage", "Cours de rattrapage"),
        ("examen", "Examen"),
        ("reunion", "Réunion"),
        ("soutenance", "Soutenance"),
        ("evenement", "Événement"),
        ("autre", "Autre"),
    ]
    salle = models.ForeignKey(
        Salle, on_delete=models.CASCADE, related_name="reservations"
    )
    demandeur = models.ForeignKey(
        Utilisateur, on_delete=models.CASCADE, related_name="reservations_locaux"
    )
    date = models.DateField()
    heure_debut = models.TimeField()
    heure_fin = models.TimeField()
    motif = models.CharField(max_length=20, choices=MOTIF_CHOICES)
    description = models.TextField(blank=True)
    nb_personnes = models.PositiveIntegerField(null=True, blank=True)
    statut = models.CharField(
        max_length=20, choices=STATUT_CHOICES, default="en_attente"
    )
    valide_par = models.ForeignKey(
        Utilisateur,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reservations_validees",
    )
    date_validation = models.DateTimeField(null=True, blank=True)
    motif_refus = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Réservation"
        verbose_name_plural = "Réservations"
        ordering = ["date", "heure_debut"]

    def __str__(self):
        return f"{self.salle.code} - {self.date} {self.heure_debut}"


class ConflitHoraire(models.Model):
    """Log des conflits d'horaires détectés."""

    TYPE_CHOICES = [
        ("salle", "Conflit de salle"),
        ("enseignant", "Conflit enseignant"),
        ("formation", "Conflit formation"),
    ]
    type_conflit = models.CharField(max_length=20, choices=TYPE_CHOICES)
    creneau_1 = models.ForeignKey(
        CreneauCours, on_delete=models.CASCADE, related_name="conflits_1"
    )
    creneau_2 = models.ForeignKey(
        CreneauCours,
        on_delete=models.CASCADE,
        related_name="conflits_2",
        null=True,
        blank=True,
    )
    reservation = models.ForeignKey(
        Reservation,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="conflits",
    )
    description = models.TextField()
    resolu = models.BooleanField(default=False)
    date_resolution = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Conflit horaire"
        verbose_name_plural = "Conflits horaires"

    def __str__(self):
        return f"{self.get_type_conflit_display()} - {self.creneau_1}"
