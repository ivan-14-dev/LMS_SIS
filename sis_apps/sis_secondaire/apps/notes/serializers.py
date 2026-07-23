"""Serializers for notes (SIS Secondaire)."""
from rest_framework import serializers
from .models import Evaluation, Note, Bulletin


class EvaluationListSerializer(serializers.ModelSerializer):
    """Serializer léger pour les listes d'évaluations."""
    matiere_nom = serializers.CharField(source='matiere.nom', read_only=True)
    classe_nom = serializers.CharField(source='classe.nom', read_only=True)
    type_display = serializers.CharField(source='get_type_display', read_only=True)
    enseignant_nom = serializers.CharField(source='enseignant.user.get_full_name', read_only=True)
    
    class Meta:
        model = Evaluation
        fields = [
            'id', 'titre', 'type', 'type_display',
            'matiere', 'matiere_nom', 'classe', 'classe_nom',
            'date', 'heure_debut', 'duree_minutes',
            'bareme', 'coefficient', 'enseignant_nom',
        ]


class EvaluationDetailSerializer(serializers.ModelSerializer):
    """Serializer complet pour une évaluation."""
    matiere_nom = serializers.CharField(source='matiere.nom', read_only=True)
    classe_nom = serializers.CharField(source='classe.nom', read_only=True)
    type_display = serializers.CharField(source='get_type_display', read_only=True)
    enseignant_nom = serializers.CharField(source='enseignant.user.get_full_name', read_only=True)
    periode_libelle = serializers.CharField(source='periode.libelle', read_only=True)
    nb_notes = serializers.SerializerMethodField()
    
    class Meta:
        model = Evaluation
        fields = [
            'id', 'titre', 'type', 'type_display', 'description',
            'matiere', 'matiere_nom', 'classe', 'classe_nom',
            'periode', 'periode_libelle',
            'date', 'heure_debut', 'duree_minutes',
            'bareme', 'coefficient',
            'enseignant', 'enseignant_nom',
            'nb_notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_nb_notes(self, obj):
        return obj.notes.exclude(valeur__isnull=True).count()


class NoteSerializer(serializers.ModelSerializer):
    """Serializer pour les notes."""
    eleve_matricule = serializers.CharField(source='eleve.matricule', read_only=True)
    eleve_nom = serializers.CharField(source='eleve.user.get_full_name', read_only=True)
    statut_display = serializers.CharField(source='get_statut_display', read_only=True)
    evaluation_titre = serializers.CharField(source='evaluation.titre', read_only=True)
    
    class Meta:
        model = Note
        fields = [
            'id', 'evaluation', 'evaluation_titre',
            'eleve', 'eleve_matricule', 'eleve_nom',
            'valeur', 'appreciation', 'statut', 'statut_display',
            'date_saisie', 'saisi_par', 'modifie_le',
        ]
        read_only_fields = ['id', 'date_saisie']


class NoteSaisieSerializer(serializers.Serializer):
    """Serializer pour la saisie en masse de notes."""
    eleve_id = serializers.IntegerField()
    valeur = serializers.DecimalField(max_digits=5, decimal_places=2, allow_null=True)
    statut = serializers.ChoiceField(choices=Note.STATUT_CHOICES, default='presente')
    appreciation = serializers.CharField(required=False, allow_blank=True)


class BulletinListSerializer(serializers.ModelSerializer):
    """Serializer léger pour les listes de bulletins."""
    eleve_matricule = serializers.CharField(source='eleve.matricule', read_only=True)
    eleve_nom = serializers.CharField(source='eleve.user.get_full_name', read_only=True)
    classe_nom = serializers.CharField(source='classe.nom', read_only=True)
    periode_libelle = serializers.CharField(source='periode.libelle', read_only=True)
    
    class Meta:
        model = Bulletin
        fields = [
            'id', 'eleve', 'eleve_matricule', 'eleve_nom',
            'classe', 'classe_nom', 'periode', 'periode_libelle',
            'moyenne_generale', 'rang', 'effectif_classe',
            'decision', 'publie', 'signe',
        ]


class BulletinDetailSerializer(serializers.ModelSerializer):
    """Serializer complet pour un bulletin."""
    eleve_matricule = serializers.CharField(source='eleve.matricule', read_only=True)
    eleve_nom = serializers.CharField(source='eleve.user.get_full_name', read_only=True)
    classe_nom = serializers.CharField(source='classe.nom', read_only=True)
    periode_libelle = serializers.CharField(source='periode.libelle', read_only=True)
    
    class Meta:
        model = Bulletin
        fields = [
            'id', 'eleve', 'eleve_matricule', 'eleve_nom',
            'classe', 'classe_nom', 'periode', 'periode_libelle',
            'moyenne_generale', 'rang', 'effectif_classe',
            'appreciation_conseil', 'decision', 'pdf_path',
            'publie', 'date_publication', 'signe', 'date_signature',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
