"""Models for etudiants (SIS Supérieur)."""
from django.db import models
from apps.etablissement.models import Universite, AnneeUniversitaire
from apps.utilisateurs.models import Utilisateur


class Etudiant(models.Model):
    """Étudiant inscrit dans l'université."""
    STATUT_CHOICES = [
        ("pre_inscrit", "Pré-inscrit"),
        ("inscrit", "Inscrit"),
        ("redoublant", "Redoublant"),
        ("suspendu", "Suspendu"),
        ("sortant", "Sortant"),
        ("diplome", "Diplômé"),
        ("abandon", "Abandon"),
        ("transfert", "Transfert"),
    ]
    REGIME_CHOICES = [
        ("formation_initiale", "Formation initiale"),
        ("formation_continue", "Formation continue"),
        ("alternance", "Alternance"),
        ("apprentissage", "Apprentissage"),
    ]
    SEXE_CHOICES = [("M", "Masculin"), ("F", "Féminin")]

    universite = models.ForeignKey(
        Universite, on_delete=models.CASCADE, related_name="etudiants"
    )
    user = models.OneToOneField(Utilisateur, on_delete=models.CASCADE, related_name="etudiant_profile")
    matricule = models.CharField(max_length=50, unique=True)
    ine = models.CharField(max_length=20, blank=True)
    date_naissance = models.DateField()
    lieu_naissance = models.CharField(max_length=200)
    sexe = models.CharField(max_length=1, choices=SEXE_CHOICES)
    nationalite = models.CharField(max_length=100, default="Française")
    adresse = models.TextField()
    code_postal = models.CharField(max_length=10)
    ville = models.CharField(max_length=100)
    pays = models.CharField(max_length=100, default="France")
    telephone = models.CharField(max_length=20)
    email_personnel = models.EmailField(blank=True)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default="pre_inscrit")
    regime = models.CharField(max_length=30, choices=REGIME_CHOICES, default="formation_initiale")
    boursier = models.BooleanField(default=False)
    date_premiere_inscription = models.DateField(null=True, blank=True)
    annee_universitaire_actuelle = models.ForeignKey(
        AnneeUniversitaire, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="etudiants_actuels",
    )
    photo = models.ImageField(upload_to="etudiants/", null=True, blank=True)
    qr_code = models.CharField(max_length=200, blank=True)
    contact_urgence_nom = models.CharField(max_length=200, blank=True)
    contact_urgence_tel = models.CharField(max_length=20, blank=True)
    numero_securite_sociale = models.CharField(max_length=20, blank=True)
    rib_iban = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["user__last_name", "user__first_name"]
        indexes = [
            models.Index(fields=["matricule"]),
            models.Index(fields=["statut"]),
        ]

    def __str__(self):
        return f"{self.matricule} - {self.user.get_full_name()}"


class InscriptionAdministrative(models.Model):
    """Inscription administrative (IA) d'un étudiant."""
    STATUT_CHOICES = [
        ("provisoire", "Provisoire"),
        ("validee", "Validée"),
        ("refusee", "Refusée"),
        ("annulee", "Annulée"),
    ]
    etudiant = models.ForeignKey(Etudiant, on_delete=models.CASCADE, related_name="inscriptions_admin")
    annee_universitaire = models.ForeignKey(
        AnneeUniversitaire, on_delete=models.PROTECT, related_name="inscriptions_admin"
    )
    formation = models.ForeignKey(
        "formations.Formation", on_delete=models.PROTECT, related_name="inscriptions_admin"
    )
    parcours = models.ForeignKey(
        "formations.Parcours", on_delete=models.PROTECT, related_name="inscriptions_admin",
        null=True, blank=True,
    )
    date_inscription = models.DateField()
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default="provisoire")
    regime = models.CharField(max_length=30, default="formation_initiale")
    bourse_id = models.CharField(max_length=50, blank=True, help_text="ID bourse CROUS")
    pieces_fournies = models.JSONField(default=list, blank=True)
    payeur = models.CharField(max_length=200, blank=True)
    motif_refus = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("etudiant", "annee_universitaire")]
        ordering = ["-annee_universitaire__date_debut"]

    def __str__(self):
        return f"IA {self.etudiant} - {self.annee_universitaire}"


class InscriptionPedagogique(models.Model):
    """Inscription pédagogique (IP) : choix des UE par l'étudiant."""
    STATUT_CHOICES = [
        ("brouillon", "Brouillon"),
        ("soumise", "Soumise"),
        ("validee", "Validée"),
        ("refusee", "Refusée"),
        ("modifiee", "Modifiée par admin"),
    ]
    inscription_admin = models.ForeignKey(
        InscriptionAdministrative, on_delete=models.CASCADE, related_name="inscriptions_peda"
    )
    semestre = models.ForeignKey(
        "etablissement.Semestre", on_delete=models.PROTECT, related_name="inscriptions_peda"
    )
    ues = models.ManyToManyField("ue_ecue.UE", related_name="inscriptions_peda")
    ecues = models.ManyToManyField("ue_ecue.ECUE", blank=True, related_name="inscriptions_peda")
    groupe_td = models.CharField(max_length=20, blank=True)
    groupe_tp = models.CharField(max_length=20, blank=True)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default="brouillon")
    date_soumission = models.DateTimeField(null=True, blank=True)
    date_validation = models.DateTimeField(null=True, blank=True)
    validee_par = models.ForeignKey(
        Utilisateur, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="ips_validees",
    )
    motif_refus = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("inscription_admin", "semestre")]
        verbose_name = "Inscription pédagogique"
        verbose_name_plural = "Inscriptions pédagogiques"

    def __str__(self):
        return f"IP {self.inscription_admin.etudiant} - {self.semestre}"


class AcquisitionECTS(models.Model):
    """Acquisition des crédits ECTS pour un étudiant."""
    STATUT_CHOICES = [
        ("acquis", "Acquis"),
        ("en_cours", "En cours"),
        ("echec", "Échec"),
        ("dispense", "Dispensé"),
    ]
    etudiant = models.ForeignKey(Etudiant, on_delete=models.CASCADE, related_name="acquisitions_ects")
    ue = models.ForeignKey("ue_ecue.UE", on_delete=models.PROTECT, related_name="acquisitions")
    annee_universitaire = models.ForeignKey(
        AnneeUniversitaire, on_delete=models.PROTECT, related_name="acquisitions_ects"
    )
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default="en_cours")
    note = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    credits_obtenus = models.DecimalField(max_digits=4, decimal_places=2, default=0)
    date_acquisition = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("etudiant", "ue", "annee_universitaire")]
        verbose_name = "Acquisition ECTS"
        verbose_name_plural = "Acquisitions ECTS"

    def __str__(self):
        return f"{self.etudiant} - {self.ue} ({self.statut})"
