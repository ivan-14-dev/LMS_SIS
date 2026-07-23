"""Serializers for emplois_du_temps (SIS Secondaire)."""
from rest_framework import serializers
from .models import Creneau, Contrainte


class CreneauListSerializer(serializers.ModelSerializer):
    """Serializer léger pour les listes de créneaux."""
    jour_display = serializers.CharField(source='get_jour_display', read_only=True)
    type_display = serializers.CharField(source='get_type_display', read_only=True)
    classe_nom = serializers.CharField(source='classe.nom', read_only=True)
    matiere_nom = serializers.CharField(source='matiere.nom', read_only=True)
    enseignant_nom = serializers.CharField(source='enseignant.user.get_full_name', read_only=True)
    salle_nom = serializers.CharField(source='salle.nom', read_only=True)
    
    class Meta:
        model = Creneau
        fields = [
            'id', 'classe', 'classe_nom',
            'matiere', 'matiere_nom',
            'enseignant', 'enseignant_nom',
            'salle', 'salle_nom',
            'jour', 'jour_display',
            'heure_debut', 'heure_fin',
            'type', 'type_display', 'actif',
        ]


class CreneauDetailSerializer(serializers.ModelSerializer):
    """Serializer complet pour un créneau."""
    jour_display = serializers.CharField(source='get_jour_display', read_only=True)
    type_display = serializers.CharField(source='get_type_display', read_only=True)
    classe_nom = serializers.CharField(source='classe.nom', read_only=True)
    matiere_nom = serializers.CharField(source='matiere.nom', read_only=True)
    matiere_code = serializers.CharField(source='matiere.code', read_only=True)
    enseignant_nom = serializers.CharField(source='enseignant.user.get_full_name', read_only=True)
    salle_nom = serializers.CharField(source='salle.nom', read_only=True)
    
    class Meta:
        model = Creneau
        fields = [
            'id', 'classe', 'classe_nom',
            'matiere', 'matiere_nom', 'matiere_code',
            'enseignant', 'enseignant_nom',
            'salle', 'salle_nom',
            'jour', 'jour_display',
            'heure_debut', 'heure_fin', 'semaine',
            'type', 'type_display', 'date_specifique',
            'notes', 'actif', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ContrainteSerializer(serializers.ModelSerializer):
    """Serializer pour les contraintes."""
    type_display = serializers.CharField(source='get_type_display', read_only=True)
    enseignant_nom = serializers.CharField(source='enseignant.user.get_full_name', read_only=True)
    salle_nom = serializers.CharField(source='salle.nom', read_only=True)
    classe_nom = serializers.CharField(source='classe.nom', read_only=True)
    jour_display = serializers.SerializerMethodField()
    
    class Meta:
        model = Contrainte
        fields = [
            'id', 'type', 'type_display',
            'enseignant', 'enseignant_nom',
            'salle', 'salle_nom',
            'classe', 'classe_nom',
            'jour', 'jour_display',
            'heure_debut', 'heure_fin',
            'priorite', 'motif', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_jour_display(self, obj):
        if obj.jour:
            return dict(Creneau.JOUR_CHOICES).get(obj.jour, '')
        return None


class EdtClasseSerializer(serializers.Serializer):
    """Serializer pour l'EDT complet d'une classe."""
    classe_id = serializers.IntegerField()
    classe_nom = serializers.CharField()
    semaine = serializers.IntegerField(required=False, default=0)
    creneaux = CreneauListSerializer(many=True)
