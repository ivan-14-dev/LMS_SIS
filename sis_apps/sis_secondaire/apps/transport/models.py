"""Models for transport (SIS Secondaire)."""
from django.db import models
from apps.eleves.models import Eleve


class LigneTransport(models.Model):
    """Ligne de transport scolaire."""
    nom = models.CharField(max_length=200)
    itineraire = models.TextField()
    distance_km = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    duree_estimee_min = models.PositiveIntegerField(default=0)
    couleur = models.CharField(max_length=7, default="#3B82F6")
    actif = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Ligne de transport"
        verbose_name_plural = "Lignes de transport"
        ordering = ["nom"]

    def __str__(self):
        return self.nom


class Arret(models.Model):
    """Arrêt sur une ligne."""
    ligne = models.ForeignKey(LigneTransport, on_delete=models.CASCADE, related_name="arrets")
    nom = models.CharField(max_length=200)
    heure_passage = models.TimeField()
    ordre = models.PositiveIntegerField()
    adresse = models.TextField(blank=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)

    class Meta:
        unique_together = [("ligne", "ordre")]
        ordering = ["ligne", "ordre"]
        verbose_name = "Arrêt"
        verbose_name_plural = "Arrêts"

    def __str__(self):
        return f"{self.ligne.nom} - {self.nom}"


class Vehicule(models.Model):
    """Bus / véhicule scolaire."""
    immatriculation = models.CharField(max_length=20, unique=True)
    modele = models.CharField(max_length=100, blank=True)
    marque = models.CharField(max_length=100, blank=True)
    annee = models.PositiveSmallIntegerField(null=True, blank=True)
    capacite = models.PositiveIntegerField(default=50)
    chauffeur = models.CharField(max_length=200, blank=True)
    telephone_chauffeur = models.CharField(max_length=20, blank=True)
    gps_actif = models.BooleanField(default=False)
    ligne = models.ForeignKey(
        LigneTransport, on_delete=models.SET_NULL, null=True, blank=True, related_name="vehicules"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Véhicule"
        verbose_name_plural = "Véhicules"

    def __str__(self):
        return f"{self.immatriculation} - {self.modele}"


class InscriptionTransport(models.Model):
    """Inscription d'un élève à une ligne."""
    eleve = models.ForeignKey(Eleve, on_delete=models.CASCADE, related_name="inscriptions_transport")
    ligne = models.ForeignKey(LigneTransport, on_delete=models.CASCADE, related_name="inscriptions")
    arret_montee = models.ForeignKey(
        Arret, on_delete=models.PROTECT, related_name="montées"
    )
    arret_descente = models.ForeignKey(
        Arret, on_delete=models.PROTECT, related_name="descentes"
    )
    annee_scolaire = models.ForeignKey(
        "etablissement.AnneeScolaire", on_delete=models.CASCADE, related_name="inscriptions_transport"
    )
    actif = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("eleve", "annee_scolaire")]
        verbose_name = "Inscription transport"
        verbose_name_plural = "Inscriptions transport"

    def __str__(self):
        return f"{self.eleve} - {self.ligne}"
