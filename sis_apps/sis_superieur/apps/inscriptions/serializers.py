"""Serializers for inscriptions (SIS Supérieur).

Note: Ce module utilise InscriptionAdministrative du module etudiants.
Il fournit des vues spécialisées pour le workflow d'inscription.
"""
from rest_framework import serializers
from apps.etudiants.models import InscriptionAdministrative


class InscriptionSerializer(serializers.ModelSerializer):
    """Serializer pour les inscriptions administratives."""
    etudiant_matricule = serializers.CharField(source='etudiant.matricule', read_only=True)
    etudiant_nom = serializers.CharField(source='etudiant.user.get_full_name', read_only=True)
    formation_nom = serializers.CharField(source='formation.nom', read_only=True)
    annee_libelle = serializers.CharField(source='annee_universitaire.libelle', read_only=True)
    statut_display = serializers.CharField(source='get_statut_display', read_only=True)
    
    class Meta:
        model = InscriptionAdministrative
        fields = [
            'id', 'etudiant', 'etudiant_matricule', 'etudiant_nom',
            'formation', 'formation_nom',
            'parcours', 'annee_universitaire', 'annee_libelle',
            'annee_etude', 'statut', 'statut_display',
            'date_inscription', 'active', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']
