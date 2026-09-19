"""Models for mobilite internationale (SIS Supérieur)."""

from apps.etablissement.models import AnneeUniversitaire
from apps.etudiants.models import Etudiant
from apps.formations.models import Formation
from apps.ue_ecue.models import UE
from apps.utilisateurs.models import Utilisateur
from django.db import models


class ProgrammeMobilite(models.Model):
    """Programme de mobilité (ERASMUS+, etc.)."""

    TYPE_CHOICES = [
        ("erasmus", "ERASMUS+"),
        ("erasmus_mundus", "ERASMUS Mundus"),
        ("bilateral", "Convention bilatérale"),
        ("propre", "Programme propre"),
        ("crepuq", "CREPUQ"),
        ("fulbright", "Fulbright"),
    ]
    formation = models.ForeignKey(
        Formation, on_delete=models.CASCADE, related_name="programmes_mobilite"
    )
    nom = models.CharField(max_length=200)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    universite_accueil = models.CharField(max_length=200)
    pays = models.CharField(max_length=100)
    duree_mois = models.PositiveSmallIntegerField()
    nb_places = models.PositiveSmallIntegerField(default=1)
    langue_requise = models.CharField(max_length=50, default="Anglais")
    niveau_langue = models.CharField(max_length=10, default="B2")
    description = models.TextField(blank=True)
    date_limite_candidature = models.DateField()
    annee_universitaire = models.ForeignKey(
        AnneeUniversitaire, on_delete=models.CASCADE, related_name="programmes_mobilite"
    )
    actif = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Programme de mobilité"
        verbose_name_plural = "Programmes de mobilité"

    def __str__(self):
        return f"{self.nom} - {self.universite_accueil}"


class CandidatureMobilite(models.Model):
    """Candidature d'un étudiant à un programme de mobilité."""

    STATUT_CHOICES = [
        ("brouillon", "Brouillon"),
        ("soumise", "Soumise"),
        ("preselectionne", "Présélectionné"),
        ("acceptee", "Acceptée"),
        ("refusee", "Refusée"),
        ("annulee", "Annulée"),
        ("en_mobilite", "En mobilité"),
        ("terminee", "Terminée"),
    ]
    etudiant = models.ForeignKey(
        Etudiant, on_delete=models.CASCADE, related_name="candidatures_mobilite"
    )
    programme = models.ForeignKey(
        ProgrammeMobilite, on_delete=models.CASCADE, related_name="candidatures"
    )
    lettre_motivation = models.TextField()
    cv = models.FileField(upload_to="mobilite/cv/")
    releve_notes = models.FileField(upload_to="mobilite/releves/")
    certificat_langue = models.FileField(
        upload_to="mobilite/langues/", null=True, blank=True
    )
    projet_personnel = models.TextField()
    moyenne_ponderee = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    statut = models.CharField(
        max_length=20, choices=STATUT_CHOICES, default="brouillon"
    )
    date_soumission = models.DateTimeField(null=True, blank=True)
    decision_par = models.ForeignKey(
        Utilisateur,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="decisions_mobilite",
    )
    motif_refus = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Candidature mobilité"
        verbose_name_plural = "Candidatures mobilité"

    def __str__(self):
        return f"{self.etudiant} - {self.programme}"


class AccordEtudes(models.Model):
    """Accord d'études / Learning Agreement."""

    STATUT_CHOICES = [
        ("brouillon", "Brouillon"),
        ("soumis", "Soumis"),
        ("valide_local", "Validé par l'établissement d'origine"),
        ("valide_accueil", "Validé par l'université d'accueil"),
        ("refuse", "Refusé"),
        ("modifie", "Modifié en cours de mobilité"),
    ]
    candidature = models.OneToOneField(
        CandidatureMobilite, on_delete=models.CASCADE, related_name="accord_etudes"
    )
    pdf_signe = models.FileField(
        upload_to="mobilite/learning_agreements/", null=True, blank=True
    )
    statut = models.CharField(
        max_length=20, choices=STATUT_CHOICES, default="brouillon"
    )
    date_validation_origine = models.DateTimeField(null=True, blank=True)
    date_validation_accueil = models.DateTimeField(null=True, blank=True)
    valide_par_origine = models.ForeignKey(
        Utilisateur,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="la_valides_origine",
    )
    valide_par_accueil = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Accord d'études"
        verbose_name_plural = "Accords d'études"

    def __str__(self):
        return f"LA {self.candidature}"


class UEAccordEtudes(models.Model):
    """UE dans l'accord d'études (équivalence)."""

    VALIDATION_CHOICES = [
        ("OK", "Équivalence totale"),
        ("PARTIEL", "Équivalence partielle"),
        ("REFUS", "Refusé"),
        ("EN_ATTENTE", "En attente"),
    ]
    accord = models.ForeignKey(
        AccordEtudes, on_delete=models.CASCADE, related_name="ues"
    )
    ue_origine = models.ForeignKey(
        UE, on_delete=models.CASCADE, related_name="accords_origine"
    )
    code_universite_accueil = models.CharField(max_length=30)
    intitule_accueil = models.CharField(max_length=200)
    credits_accueil = models.DecimalField(max_digits=4, decimal_places=2)
    credits_origine = models.DecimalField(max_digits=4, decimal_places=2)
    validation = models.CharField(
        max_length=20, choices=VALIDATION_CHOICES, default="EN_ATTENTE"
    )
    note_obtenue_accueil = models.DecimalField(
        max_digits=4, decimal_places=2, null=True, blank=True
    )
    note_echelle_ects = models.CharField(
        max_length=2, blank=True, help_text="A, B, C, D, E, F"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "UE accord d'études"
        verbose_name_plural = "UEs accord d'études"

    def __str__(self):
        return f"{self.ue_origine} ↔ {self.intitule_accueil}"
