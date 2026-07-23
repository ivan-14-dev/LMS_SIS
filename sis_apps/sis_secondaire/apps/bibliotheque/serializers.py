"""Serializers for bibliotheque (SIS Secondaire)."""
from rest_framework import serializers
from .models import Livre, Exemplaire, Emprunt


class LivreListSerializer(serializers.ModelSerializer):
    """Serializer léger pour les listes de livres."""
    nb_exemplaires = serializers.SerializerMethodField()
    disponibles = serializers.SerializerMethodField()
    
    class Meta:
        model = Livre
        fields = [
            'id', 'isbn', 'titre', 'auteurs', 'editeur',
            'annee', 'categorie', 'cote',
            'nb_exemplaires', 'disponibles',
        ]
    
    def get_nb_exemplaires(self, obj):
        return obj.exemplaires.exclude(etat='perdu').count()
    
    def get_disponibles(self, obj):
        return obj.exemplaires.exclude(
            etat='perdu'
        ).exclude(
            emprunts__statut='en_cours'
        ).count()


class LivreDetailSerializer(serializers.ModelSerializer):
    """Serializer complet pour un livre."""
    exemplaires = serializers.SerializerMethodField()
    
    class Meta:
        model = Livre
        fields = [
            'id', 'isbn', 'titre', 'auteurs', 'editeur',
            'annee', 'categorie', 'mots_cles', 'resume',
            'image_couverture', 'cote', 'nombre_exemplaires',
            'exemplaires', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_exemplaires(self, obj):
        return ExemplaireSerializer(obj.exemplaires.all(), many=True).data


class ExemplaireSerializer(serializers.ModelSerializer):
    """Serializer pour les exemplaires."""
    livre_titre = serializers.CharField(source='livre.titre', read_only=True)
    etat_display = serializers.CharField(source='get_etat_display', read_only=True)
    disponible = serializers.SerializerMethodField()
    
    class Meta:
        model = Exemplaire
        fields = [
            'id', 'livre', 'livre_titre',
            'code_barre', 'etat', 'etat_display',
            'localisation', 'date_acquisition',
            'disponible', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_disponible(self, obj):
        return not obj.emprunts.filter(statut='en_cours').exists()


class EmpruntSerializer(serializers.ModelSerializer):
    """Serializer pour les emprunts."""
    exemplaire_code = serializers.CharField(source='exemplaire.code_barre', read_only=True)
    livre_titre = serializers.CharField(source='exemplaire.livre.titre', read_only=True)
    emprunteur_nom = serializers.CharField(source='emprunteur.get_full_name', read_only=True)
    statut_display = serializers.CharField(source='get_statut_display', read_only=True)
    jours_retard = serializers.SerializerMethodField()
    
    class Meta:
        model = Emprunt
        fields = [
            'id', 'exemplaire', 'exemplaire_code', 'livre_titre',
            'emprunteur', 'emprunteur_nom',
            'date_emprunt', 'date_retour_prevue', 'date_retour_reelle',
            'statut', 'statut_display', 'nb_renouvellements',
            'penalite', 'jours_retard', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_jours_retard(self, obj):
        if obj.statut != 'en_cours':
            return 0
        from django.utils import timezone
        today = timezone.now().date()
        if today > obj.date_retour_prevue:
            return (today - obj.date_retour_prevue).days
        return 0
