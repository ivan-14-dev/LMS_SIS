"""Serializers for UE/ECUE (SIS Supérieur)."""
from rest_framework import serializers
from .models import UE, ECUE, Prerequis


class UEListSerializer(serializers.ModelSerializer):
    """Serializer léger pour les UE."""
    type_display = serializers.CharField(source='get_type_display', read_only=True)
    semestre_libelle = serializers.CharField(source='semestre.libelle', read_only=True)
    formation_nom = serializers.CharField(source='maquette.formation.nom', read_only=True)
    volume_horaire_total = serializers.IntegerField(read_only=True)
    nb_ecues = serializers.SerializerMethodField()
    
    class Meta:
        model = UE
        fields = [
            'id', 'code', 'nom', 'credits_ects',
            'type', 'type_display',
            'semestre', 'semestre_libelle',
            'maquette', 'formation_nom',
            'volume_horaire_cm', 'volume_horaire_td', 'volume_horaire_tp',
            'volume_horaire_total', 'nb_ecues',
        ]
    
    def get_nb_ecues(self, obj):
        return obj.ecues.count()


class UEDetailSerializer(serializers.ModelSerializer):
    """Serializer complet pour une UE."""
    type_display = serializers.CharField(source='get_type_display', read_only=True)
    mh_global_display = serializers.CharField(source='get_mh_global_display', read_only=True)
    semestre_libelle = serializers.CharField(source='semestre.libelle', read_only=True)
    formation_nom = serializers.CharField(source='maquette.formation.nom', read_only=True)
    volume_horaire_total = serializers.IntegerField(read_only=True)
    nb_ecues = serializers.SerializerMethodField()
    parcours_noms = serializers.SerializerMethodField()
    
    class Meta:
        model = UE
        fields = [
            'id', 'code', 'nom', 'credits_ects',
            'type', 'type_display',
            'semestre', 'semestre_libelle',
            'maquette', 'formation_nom',
            'volume_horaire_cm', 'volume_horaire_td', 'volume_horaire_tp',
            'volume_horaire_total', 'mh_global', 'mh_global_display',
            'parcours_autorises', 'parcours_noms',
            'description', 'nb_ecues', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_nb_ecues(self, obj):
        return obj.ecues.count()
    
    def get_parcours_noms(self, obj):
        return [p.nom for p in obj.parcours_autorises.all()]


class ECUESerializer(serializers.ModelSerializer):
    """Serializer pour les ECUE."""
    ue_code = serializers.CharField(source='ue.code', read_only=True)
    ue_nom = serializers.CharField(source='ue.nom', read_only=True)
    volume_horaire_total = serializers.SerializerMethodField()
    
    class Meta:
        model = ECUE
        fields = [
            'id', 'code', 'nom', 'credits_ects', 'coefficient',
            'ue', 'ue_code', 'ue_nom',
            'volume_horaire_cm', 'volume_horaire_td', 'volume_horaire_tp',
            'volume_horaire_total',
            'description', 'programme', 'bibliographie',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_volume_horaire_total(self, obj):
        return obj.volume_horaire_cm + obj.volume_horaire_td + obj.volume_horaire_tp


class PrerequisSerializer(serializers.ModelSerializer):
    """Serializer pour les prérequis."""
    ue_cible_code = serializers.CharField(source='ue_cible.code', read_only=True)
    ue_cible_nom = serializers.CharField(source='ue_cible.nom', read_only=True)
    ue_prereq_code = serializers.CharField(source='ue_prereq.code', read_only=True)
    ue_prereq_nom = serializers.CharField(source='ue_prereq.nom', read_only=True)
    type_display = serializers.CharField(source='get_type_display', read_only=True)
    
    class Meta:
        model = Prerequis
        fields = [
            'id', 'ue_cible', 'ue_cible_code', 'ue_cible_nom',
            'ue_prereq', 'ue_prereq_code', 'ue_prereq_nom',
            'type', 'type_display', 'note_minimale', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']
