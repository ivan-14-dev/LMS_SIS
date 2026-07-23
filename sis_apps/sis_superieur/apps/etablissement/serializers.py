"""Serializers for etablissement (SIS Supérieur)."""
from rest_framework import serializers
from .models import Universite, AnneeUniversitaire, Semestre


class UniversiteSerializer(serializers.ModelSerializer):
    """Serializer pour les universités."""
    type_display = serializers.CharField(source='get_type_display', read_only=True)
    nb_facultes = serializers.SerializerMethodField()
    
    class Meta:
        model = Universite
        fields = [
            'id', 'nom', 'sigle', 'type', 'type_display',
            'ministere_tutelle', 'uai',
            'adresse', 'code_postal', 'ville', 'pays',
            'telephone', 'email', 'site_web', 'logo',
            'systeme_notation', 'credits_annee',
            'accreditations', 'conventions_internationales',
            'nb_facultes', 'actif', 'date_creation',
        ]
        read_only_fields = ['id', 'date_creation']
    
    def get_nb_facultes(self, obj):
        return obj.facultes.count() if hasattr(obj, 'facultes') else 0


class AnneeUniversitaireSerializer(serializers.ModelSerializer):
    """Serializer pour les années universitaires."""
    nb_semestres = serializers.SerializerMethodField()
    
    class Meta:
        model = AnneeUniversitaire
        fields = [
            'id', 'universite', 'libelle',
            'date_debut', 'date_fin',
            'en_cours', 'cloturee',
            'nb_semestres', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_nb_semestres(self, obj):
        return obj.semestres.count()


class SemestreSerializer(serializers.ModelSerializer):
    """Serializer pour les semestres."""
    annee_libelle = serializers.CharField(source='annee_universitaire.libelle', read_only=True)
    type_display = serializers.CharField(source='get_type_display', read_only=True)
    libelle = serializers.SerializerMethodField()
    
    class Meta:
        model = Semestre
        fields = [
            'id', 'annee_universitaire', 'annee_libelle',
            'numero', 'type', 'type_display', 'libelle',
            'date_debut', 'date_fin', 'cloture', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_libelle(self, obj):
        return str(obj)
