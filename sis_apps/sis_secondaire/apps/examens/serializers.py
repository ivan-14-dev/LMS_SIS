"""Serializers for examens (SIS Secondaire)."""
from rest_framework import serializers
from .models import SessionExamen, EpreuveExamen, ConvocationExamen, ResultatExamen


class SessionExamenSerializer(serializers.ModelSerializer):
    """Serializer pour les sessions d'examen."""
    type_display = serializers.CharField(source='get_type_display', read_only=True)
    annee_libelle = serializers.CharField(source='annee_scolaire.libelle', read_only=True)
    nb_epreuves = serializers.SerializerMethodField()
    
    class Meta:
        model = SessionExamen
        fields = [
            'id', 'annee_scolaire', 'annee_libelle',
            'type', 'type_display', 'nom',
            'date_debut', 'date_fin', 'nb_epreuves', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_nb_epreuves(self, obj):
        return obj.epreuves.count()


class EpreuveExamenListSerializer(serializers.ModelSerializer):
    """Serializer léger pour les épreuves."""
    session_nom = serializers.CharField(source='session.nom', read_only=True)
    matiere_nom = serializers.CharField(source='matiere.nom', read_only=True)
    salle_nom = serializers.CharField(source='salle_principale.nom', read_only=True)
    
    class Meta:
        model = EpreuveExamen
        fields = [
            'id', 'session', 'session_nom',
            'matiere', 'matiere_nom',
            'date', 'heure_debut', 'duree_minutes',
            'salle_principale', 'salle_nom',
            'bareme', 'coefficient', 'anonymat',
        ]


class EpreuveExamenDetailSerializer(serializers.ModelSerializer):
    """Serializer complet pour une épreuve."""
    session_nom = serializers.CharField(source='session.nom', read_only=True)
    matiere_nom = serializers.CharField(source='matiere.nom', read_only=True)
    classes_list = serializers.SerializerMethodField()
    surveillants_list = serializers.SerializerMethodField()
    
    class Meta:
        model = EpreuveExamen
        fields = [
            'id', 'session', 'session_nom',
            'matiere', 'matiere_nom',
            'classes', 'classes_list',
            'date', 'heure_debut', 'duree_minutes',
            'salle_principale', 'bareme', 'coefficient',
            'surveillants', 'surveillants_list', 'anonymat', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_classes_list(self, obj):
        return [{'id': c.id, 'nom': c.nom} for c in obj.classes.all()]
    
    def get_surveillants_list(self, obj):
        return [{'id': s.id, 'nom': s.get_full_name()} for s in obj.surveillants.all()]


class ConvocationExamenSerializer(serializers.ModelSerializer):
    """Serializer pour les convocations."""
    epreuve_info = serializers.SerializerMethodField()
    eleve_matricule = serializers.CharField(source='eleve.matricule', read_only=True)
    eleve_nom = serializers.CharField(source='eleve.user.get_full_name', read_only=True)
    statut_display = serializers.CharField(source='get_statut_display', read_only=True)
    
    class Meta:
        model = ConvocationExamen
        fields = [
            'id', 'epreuve', 'epreuve_info',
            'eleve', 'eleve_matricule', 'eleve_nom',
            'numero_place', 'salle',
            'statut', 'statut_display',
            'notifie_parents', 'date_notification',
        ]
        read_only_fields = ['id']
    
    def get_epreuve_info(self, obj):
        return {
            'matiere': obj.epreuve.matiere.nom,
            'date': obj.epreuve.date,
            'heure': str(obj.epreuve.heure_debut),
        }


class ResultatExamenSerializer(serializers.ModelSerializer):
    """Serializer pour les résultats."""
    epreuve_matiere = serializers.CharField(source='epreuve.matiere.nom', read_only=True)
    eleve_matricule = serializers.CharField(source='eleve.matricule', read_only=True)
    eleve_nom = serializers.CharField(source='eleve.user.get_full_name', read_only=True)
    
    class Meta:
        model = ResultatExamen
        fields = [
            'id', 'epreuve', 'epreuve_matiere',
            'eleve', 'eleve_matricule', 'eleve_nom',
            'note', 'appreciation', 'numero_anonyme',
            'admis', 'mention', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']
