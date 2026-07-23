"""Serializers for discipline (SIS Secondaire)."""
from rest_framework import serializers
from .models import Incident, Sanction, ConseilDiscipline


class IncidentListSerializer(serializers.ModelSerializer):
    """Serializer léger pour les listes d'incidents."""
    eleve_matricule = serializers.CharField(source='eleve.matricule', read_only=True)
    eleve_nom = serializers.CharField(source='eleve.user.get_full_name', read_only=True)
    eleve_classe = serializers.CharField(source='eleve.classe.nom', read_only=True)
    type_display = serializers.CharField(source='get_type_display', read_only=True)
    gravite_display = serializers.CharField(source='get_gravite_display', read_only=True)
    statut_display = serializers.CharField(source='get_statut_display', read_only=True)
    rapporteur_nom = serializers.CharField(source='rapporteur.user.get_full_name', read_only=True)
    
    class Meta:
        model = Incident
        fields = [
            'id', 'eleve', 'eleve_matricule', 'eleve_nom', 'eleve_classe',
            'date_incident', 'type', 'type_display',
            'gravite', 'gravite_display',
            'statut', 'statut_display',
            'rapporteur', 'rapporteur_nom',
        ]


class IncidentDetailSerializer(serializers.ModelSerializer):
    """Serializer complet pour un incident."""
    eleve_matricule = serializers.CharField(source='eleve.matricule', read_only=True)
    eleve_nom = serializers.CharField(source='eleve.user.get_full_name', read_only=True)
    eleve_classe = serializers.CharField(source='eleve.classe.nom', read_only=True)
    type_display = serializers.CharField(source='get_type_display', read_only=True)
    gravite_display = serializers.CharField(source='get_gravite_display', read_only=True)
    statut_display = serializers.CharField(source='get_statut_display', read_only=True)
    rapporteur_nom = serializers.CharField(source='rapporteur.user.get_full_name', read_only=True)
    temoins_noms = serializers.SerializerMethodField()
    nb_sanctions = serializers.SerializerMethodField()
    
    class Meta:
        model = Incident
        fields = [
            'id', 'eleve', 'eleve_matricule', 'eleve_nom', 'eleve_classe',
            'date_incident', 'type', 'type_display',
            'gravite', 'gravite_display', 'description', 'lieu',
            'temoins', 'temoins_noms',
            'rapporteur', 'rapporteur_nom',
            'statut', 'statut_display', 'nb_sanctions',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_temoins_noms(self, obj):
        return [t.user.get_full_name() for t in obj.temoins.all()]
    
    def get_nb_sanctions(self, obj):
        return obj.sanctions.count()


class SanctionSerializer(serializers.ModelSerializer):
    """Serializer pour les sanctions."""
    eleve_nom = serializers.CharField(source='incident.eleve.user.get_full_name', read_only=True)
    type_display = serializers.CharField(source='get_type_display', read_only=True)
    incident_date = serializers.DateTimeField(source='incident.date_incident', read_only=True)
    incident_type = serializers.CharField(source='incident.get_type_display', read_only=True)
    
    class Meta:
        model = Sanction
        fields = [
            'id', 'incident', 'incident_date', 'incident_type',
            'eleve_nom', 'type', 'type_display',
            'duree_jours', 'date_effet', 'date_fin',
            'motif', 'notifiee_parents', 'date_notification',
            'executee', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class ConseilDisciplineListSerializer(serializers.ModelSerializer):
    """Serializer léger pour les conseils de discipline."""
    eleve_nom = serializers.CharField(source='eleve.user.get_full_name', read_only=True)
    eleve_classe = serializers.CharField(source='eleve.classe.nom', read_only=True)
    president_nom = serializers.CharField(source='president.user.get_full_name', read_only=True)
    statut_display = serializers.CharField(source='get_statut_display', read_only=True)
    
    class Meta:
        model = ConseilDiscipline
        fields = [
            'id', 'eleve', 'eleve_nom', 'eleve_classe',
            'date', 'president', 'president_nom',
            'statut', 'statut_display',
        ]


class ConseilDisciplineDetailSerializer(serializers.ModelSerializer):
    """Serializer complet pour un conseil de discipline."""
    eleve_nom = serializers.CharField(source='eleve.user.get_full_name', read_only=True)
    eleve_classe = serializers.CharField(source='eleve.classe.nom', read_only=True)
    president_nom = serializers.CharField(source='president.user.get_full_name', read_only=True)
    membres_noms = serializers.SerializerMethodField()
    incidents_details = serializers.SerializerMethodField()
    sanction_type = serializers.CharField(source='sanction.get_type_display', read_only=True)
    
    class Meta:
        model = ConseilDiscipline
        fields = [
            'id', 'eleve', 'eleve_nom', 'eleve_classe',
            'date', 'president', 'president_nom',
            'membres', 'membres_noms',
            'incidents', 'incidents_details',
            'sanction', 'sanction_type', 'pv', 'statut',
        ]
        read_only_fields = ['id']
    
    def get_membres_noms(self, obj):
        return [m.user.get_full_name() for m in obj.membres.all()]
    
    def get_incidents_details(self, obj):
        return [{
            'id': i.id,
            'date': i.date_incident,
            'type': i.get_type_display(),
            'gravite': i.get_gravite_display(),
        } for i in obj.incidents.all()]
