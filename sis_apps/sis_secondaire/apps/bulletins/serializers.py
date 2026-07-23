"""Serializers for bulletins (SIS Secondaire)."""
from rest_framework import serializers
from .models import AppreciationMatiere


class AppreciationMatiereSerializer(serializers.ModelSerializer):
    """Serializer pour les appréciations par matière."""
    eleve_matricule = serializers.CharField(source='eleve.matricule', read_only=True)
    eleve_nom = serializers.CharField(source='eleve.user.get_full_name', read_only=True)
    matiere_nom = serializers.CharField(source='matiere.nom', read_only=True)
    periode_nom = serializers.CharField(source='periode.nom', read_only=True)
    
    class Meta:
        model = AppreciationMatiere
        fields = [
            'id', 'eleve', 'eleve_matricule', 'eleve_nom',
            'matiere', 'matiere_nom',
            'periode', 'periode_nom',
            'appreciation', 'moyenne_matiere', 'moyenne_classe',
            'rang', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class AppreciationMatiereCreateSerializer(serializers.ModelSerializer):
    """Serializer pour créer/modifier une appréciation."""
    
    class Meta:
        model = AppreciationMatiere
        fields = [
            'id', 'eleve', 'matiere', 'periode',
            'appreciation', 'moyenne_matiere', 'moyenne_classe', 'rang',
        ]
        read_only_fields = ['id']
