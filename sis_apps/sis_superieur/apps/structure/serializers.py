"""Serializers for structure (SIS Supérieur)."""
from rest_framework import serializers
from .models import Faculte, Departement, EcoleDoctorale


class FaculteListSerializer(serializers.ModelSerializer):
    """Serializer léger pour les facultés."""
    universite_nom = serializers.CharField(source='universite.nom', read_only=True)
    doyen_nom = serializers.CharField(source='doyen.get_full_name', read_only=True)
    nb_departements = serializers.SerializerMethodField()
    
    class Meta:
        model = Faculte
        fields = [
            'id', 'code', 'nom', 'universite', 'universite_nom',
            'doyen', 'doyen_nom', 'actif', 'nb_departements',
        ]
    
    def get_nb_departements(self, obj):
        return obj.departements.count()


class FaculteDetailSerializer(serializers.ModelSerializer):
    """Serializer complet pour une faculté."""
    universite_nom = serializers.CharField(source='universite.nom', read_only=True)
    doyen_nom = serializers.CharField(source='doyen.get_full_name', read_only=True)
    nb_departements = serializers.SerializerMethodField()
    
    class Meta:
        model = Faculte
        fields = [
            'id', 'code', 'nom', 'universite', 'universite_nom',
            'doyen', 'doyen_nom', 'date_creation', 'description',
            'actif', 'nb_departements', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_nb_departements(self, obj):
        return obj.departements.count()


class DepartementSerializer(serializers.ModelSerializer):
    """Serializer pour les départements."""
    faculte_nom = serializers.CharField(source='faculte.nom', read_only=True)
    directeur_nom = serializers.CharField(source='directeur.get_full_name', read_only=True)
    
    class Meta:
        model = Departement
        fields = [
            'id', 'code', 'nom', 'faculte', 'faculte_nom',
            'directeur', 'directeur_nom', 'description',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class EcoleDoctoraleSerializer(serializers.ModelSerializer):
    """Serializer pour les écoles doctorales."""
    universite_nom = serializers.CharField(source='universite.nom', read_only=True)
    directeur_nom = serializers.CharField(source='directeur.get_full_name', read_only=True)
    
    class Meta:
        model = EcoleDoctorale
        fields = [
            'id', 'code', 'nom', 'universite', 'universite_nom',
            'directeur', 'directeur_nom', 'domaines', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']
