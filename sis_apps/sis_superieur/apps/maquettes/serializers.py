"""Serializers for maquettes (SIS Supérieur).

Note: Ce module utilise MaquetteFormation du module formations.
Il fournit des vues spécialisées pour la gestion des maquettes pédagogiques.
"""
from rest_framework import serializers
from apps.formations.models import MaquetteFormation


class MaquetteSerializer(serializers.ModelSerializer):
    """Serializer pour les maquettes de formation."""
    formation_nom = serializers.CharField(source='formation.nom', read_only=True)
    semestre_nom = serializers.CharField(source='semestre.__str__', read_only=True)
    ecue_nom = serializers.CharField(source='ecue.nom', read_only=True)
    ue_nom = serializers.CharField(source='ecue.ue.nom', read_only=True)
    
    class Meta:
        model = MaquetteFormation
        fields = [
            'id', 'formation', 'formation_nom',
            'semestre', 'semestre_nom',
            'ecue', 'ecue_nom', 'ue_nom',
            'obligatoire', 'ordre', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']
