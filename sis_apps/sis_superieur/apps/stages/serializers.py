"""Serializers for stages (SIS Supérieur)."""
from rest_framework import serializers
from .models import OffreStage, CandidatureStage, ConventionStage


class OffreStageListSerializer(serializers.ModelSerializer):
    """Serializer léger pour les listes d'offres."""
    type_display = serializers.CharField(source='get_type_display', read_only=True)
    statut_display = serializers.CharField(source='get_statut_display', read_only=True)
    entreprise_nom = serializers.CharField(source='entreprise.raison_sociale', read_only=True)
    formation_nom = serializers.CharField(source='formation.nom', read_only=True)
    nb_candidatures = serializers.SerializerMethodField()
    
    class Meta:
        model = OffreStage
        fields = [
            'id', 'titre', 'type', 'type_display',
            'entreprise', 'entreprise_nom',
            'formation', 'formation_nom',
            'lieu', 'pays', 'duree_mois',
            'date_debut', 'date_fin', 'date_limite_candidature',
            'remuneration', 'devise', 'nb_places',
            'statut', 'statut_display', 'nb_candidatures',
        ]
    
    def get_nb_candidatures(self, obj):
        return obj.candidatures.count()


class OffreStageDetailSerializer(serializers.ModelSerializer):
    """Serializer complet pour une offre de stage."""
    type_display = serializers.CharField(source='get_type_display', read_only=True)
    statut_display = serializers.CharField(source='get_statut_display', read_only=True)
    entreprise_nom = serializers.CharField(source='entreprise.raison_sociale', read_only=True)
    formation_nom = serializers.CharField(source='formation.nom', read_only=True)
    nb_candidatures = serializers.SerializerMethodField()
    
    class Meta:
        model = OffreStage
        fields = [
            'id', 'titre', 'type', 'type_display',
            'entreprise', 'entreprise_nom',
            'formation', 'formation_nom',
            'description', 'missions', 'competences_requises',
            'lieu', 'pays', 'duree_mois',
            'date_debut', 'date_fin', 'date_limite_candidature',
            'remuneration', 'devise', 'nb_places', 'reference',
            'statut', 'statut_display', 'publiee',
            'nb_candidatures', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_nb_candidatures(self, obj):
        return obj.candidatures.count()


class CandidatureStageSerializer(serializers.ModelSerializer):
    """Serializer pour les candidatures."""
    etudiant_matricule = serializers.CharField(source='etudiant.matricule', read_only=True)
    etudiant_nom = serializers.CharField(source='etudiant.user.get_full_name', read_only=True)
    offre_titre = serializers.CharField(source='offre.titre', read_only=True)
    offre_entreprise = serializers.CharField(source='offre.entreprise.raison_sociale', read_only=True)
    statut_display = serializers.CharField(source='get_statut_display', read_only=True)
    
    class Meta:
        model = CandidatureStage
        fields = [
            'id', 'etudiant', 'etudiant_matricule', 'etudiant_nom',
            'offre', 'offre_titre', 'offre_entreprise',
            'lettre_motivation', 'cv',
            'statut', 'statut_display',
            'date_soumission', 'date_reponse', 'motif_refus',
            'created_at',
        ]
        read_only_fields = ['id', 'date_soumission', 'created_at']


class ConventionStageListSerializer(serializers.ModelSerializer):
    """Serializer léger pour les conventions."""
    etudiant_nom = serializers.CharField(source='etudiant.user.get_full_name', read_only=True)
    entreprise_nom = serializers.CharField(source='entreprise.raison_sociale', read_only=True)
    offre_titre = serializers.CharField(source='offre.titre', read_only=True)
    statut_display = serializers.CharField(source='get_statut_display', read_only=True)
    
    class Meta:
        model = ConventionStage
        fields = [
            'id', 'etudiant', 'etudiant_nom',
            'entreprise', 'entreprise_nom',
            'offre', 'offre_titre',
            'statut', 'statut_display',
        ]


class ConventionStageDetailSerializer(serializers.ModelSerializer):
    """Serializer complet pour une convention."""
    etudiant_nom = serializers.CharField(source='etudiant.user.get_full_name', read_only=True)
    entreprise_nom = serializers.CharField(source='entreprise.raison_sociale', read_only=True)
    offre_titre = serializers.CharField(source='offre.titre', read_only=True)
    maitre_stage_nom = serializers.CharField(source='maitre_stage.nom', read_only=True)
    statut_display = serializers.CharField(source='get_statut_display', read_only=True)
    
    class Meta:
        model = ConventionStage
        fields = [
            'id', 'etudiant', 'etudiant_nom',
            'entreprise', 'entreprise_nom',
            'offre', 'offre_titre',
            'maitre_stage', 'maitre_stage_nom',
            'statut', 'statut_display',
        ]
        read_only_fields = ['id']
