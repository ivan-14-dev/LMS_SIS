"""Serializers for jurys (SIS Supérieur)."""
from rest_framework import serializers
from .models import Jury, Deliberation, DecisionJury, DecisionGlobale


class JuryListSerializer(serializers.ModelSerializer):
    """Serializer léger pour les listes de jurys."""
    semestre_libelle = serializers.CharField(source='semestre.__str__', read_only=True)
    formation_nom = serializers.CharField(source='formation.nom', read_only=True)
    president_nom = serializers.CharField(source='president.get_full_name', read_only=True)
    statut_display = serializers.CharField(source='get_statut_display', read_only=True)
    nb_membres = serializers.SerializerMethodField()
    
    class Meta:
        model = Jury
        fields = [
            'id', 'semestre', 'semestre_libelle',
            'formation', 'formation_nom', 'parcours',
            'date', 'lieu', 'president_nom',
            'statut', 'statut_display', 'nb_membres',
        ]
    
    def get_nb_membres(self, obj):
        return obj.membres.count()


class JuryDetailSerializer(serializers.ModelSerializer):
    """Serializer complet pour un jury."""
    semestre_libelle = serializers.CharField(source='semestre.__str__', read_only=True)
    formation_nom = serializers.CharField(source='formation.nom', read_only=True)
    parcours_nom = serializers.CharField(source='parcours.nom', read_only=True)
    president_nom = serializers.CharField(source='president.get_full_name', read_only=True)
    secretaire_nom = serializers.CharField(source='secretaire.get_full_name', read_only=True)
    statut_display = serializers.CharField(source='get_statut_display', read_only=True)
    membres_list = serializers.SerializerMethodField()
    
    class Meta:
        model = Jury
        fields = [
            'id', 'semestre', 'semestre_libelle',
            'formation', 'formation_nom',
            'parcours', 'parcours_nom',
            'date', 'lieu',
            'president', 'president_nom',
            'secretaire', 'secretaire_nom',
            'membres', 'membres_list', 'ordre_jour',
            'statut', 'statut_display',
            'pv_pdf', 'date_pv', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_membres_list(self, obj):
        return [{'id': m.id, 'nom': m.get_full_name()} for m in obj.membres.all()]


class DeliberationSerializer(serializers.ModelSerializer):
    """Serializer pour les délibérations."""
    jury_info = serializers.SerializerMethodField()
    
    class Meta:
        model = Deliberation
        fields = [
            'id', 'jury', 'jury_info',
            'date_ouverture', 'date_cloture',
            'nb_admis', 'nb_ajournes', 'nb_refuses',
            'notes', 'pv_pdf', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_jury_info(self, obj):
        return {
            'id': obj.jury.id,
            'formation': obj.jury.formation.nom,
            'date': obj.jury.date,
        }


class DecisionJurySerializer(serializers.ModelSerializer):
    """Serializer pour les décisions par UE."""
    etudiant_matricule = serializers.CharField(source='etudiant.matricule', read_only=True)
    etudiant_nom = serializers.CharField(source='etudiant.user.get_full_name', read_only=True)
    ue_code = serializers.CharField(source='ue.code', read_only=True)
    ue_nom = serializers.CharField(source='ue.nom', read_only=True)
    decision_display = serializers.CharField(source='get_decision_display', read_only=True)
    
    class Meta:
        model = DecisionJury
        fields = [
            'id', 'deliberation',
            'etudiant', 'etudiant_matricule', 'etudiant_nom',
            'ue', 'ue_code', 'ue_nom',
            'decision', 'decision_display', 'note',
            'commentaire', 'voix_pour', 'voix_contre', 'abstentions',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class DecisionGlobaleSerializer(serializers.ModelSerializer):
    """Serializer pour les décisions globales."""
    etudiant_matricule = serializers.CharField(source='etudiant.matricule', read_only=True)
    etudiant_nom = serializers.CharField(source='etudiant.user.get_full_name', read_only=True)
    decision_display = serializers.CharField(source='get_decision_display', read_only=True)
    
    class Meta:
        model = DecisionGlobale
        fields = [
            'id', 'deliberation',
            'etudiant', 'etudiant_matricule', 'etudiant_nom',
            'decision', 'decision_display',
            'mention', 'moyenne', 'credits_valides',
            'passage_niveau_suivant', 'commentaire', 'created_at',
        ]
