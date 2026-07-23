"""Serializers for transport (SIS Secondaire)."""
from rest_framework import serializers
from .models import LigneTransport, Arret, Vehicule, InscriptionTransport


class ArretSerializer(serializers.ModelSerializer):
    """Serializer pour les arrêts."""
    ligne_nom = serializers.CharField(source='ligne.nom', read_only=True)
    
    class Meta:
        model = Arret
        fields = [
            'id', 'ligne', 'ligne_nom',
            'nom', 'heure_passage', 'ordre',
            'adresse', 'latitude', 'longitude',
        ]
        read_only_fields = ['id']


class LigneTransportListSerializer(serializers.ModelSerializer):
    """Serializer léger pour les lignes."""
    nb_arrets = serializers.SerializerMethodField()
    nb_inscrits = serializers.SerializerMethodField()
    
    class Meta:
        model = LigneTransport
        fields = [
            'id', 'nom', 'distance_km', 'duree_estimee_min',
            'couleur', 'actif', 'nb_arrets', 'nb_inscrits',
        ]
    
    def get_nb_arrets(self, obj):
        return obj.arrets.count()
    
    def get_nb_inscrits(self, obj):
        return obj.inscriptions.filter(actif=True).count()


class LigneTransportDetailSerializer(serializers.ModelSerializer):
    """Serializer complet pour une ligne."""
    arrets = ArretSerializer(many=True, read_only=True)
    nb_inscrits = serializers.SerializerMethodField()
    
    class Meta:
        model = LigneTransport
        fields = [
            'id', 'nom', 'itineraire',
            'distance_km', 'duree_estimee_min',
            'couleur', 'actif',
            'arrets', 'nb_inscrits', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_nb_inscrits(self, obj):
        return obj.inscriptions.filter(actif=True).count()


class VehiculeSerializer(serializers.ModelSerializer):
    """Serializer pour les véhicules."""
    ligne_nom = serializers.CharField(source='ligne.nom', read_only=True)
    
    class Meta:
        model = Vehicule
        fields = [
            'id', 'immatriculation', 'modele', 'marque', 'annee',
            'capacite', 'chauffeur', 'telephone_chauffeur',
            'gps_actif', 'ligne', 'ligne_nom', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class InscriptionTransportSerializer(serializers.ModelSerializer):
    """Serializer pour les inscriptions transport."""
    eleve_matricule = serializers.CharField(source='eleve.matricule', read_only=True)
    eleve_nom = serializers.CharField(source='eleve.user.get_full_name', read_only=True)
    eleve_classe = serializers.CharField(source='eleve.classe.nom', read_only=True)
    ligne_nom = serializers.CharField(source='ligne.nom', read_only=True)
    arret_montee_nom = serializers.CharField(source='arret_montee.nom', read_only=True)
    arret_descente_nom = serializers.CharField(source='arret_descente.nom', read_only=True)
    
    class Meta:
        model = InscriptionTransport
        fields = [
            'id', 'eleve', 'eleve_matricule', 'eleve_nom', 'eleve_classe',
            'ligne', 'ligne_nom',
            'arret_montee', 'arret_montee_nom',
            'arret_descente', 'arret_descente_nom',
            'annee_scolaire', 'actif', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']
