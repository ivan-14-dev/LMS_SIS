"""Serializers for rattrapages (SIS Supérieur)."""
from rest_framework import serializers
from .models import InscriptionRattrapage


class InscriptionRattrapageSerializer(serializers.ModelSerializer):
    """Serializer pour les inscriptions au rattrapage."""
    etudiant_matricule = serializers.CharField(source='etudiant.matricule', read_only=True)
    etudiant_nom = serializers.CharField(source='etudiant.user.get_full_name', read_only=True)
    ecue_code = serializers.CharField(source='ecue.code', read_only=True)
    ecue_nom = serializers.CharField(source='ecue.nom', read_only=True)
    session_libelle = serializers.CharField(source='session_rattrapage.libelle', read_only=True)
    statut_display = serializers.CharField(source='get_statut_display', read_only=True)
    
    class Meta:
        model = InscriptionRattrapage
        fields = [
            'id', 'etudiant', 'etudiant_matricule', 'etudiant_nom',
            'ecue', 'ecue_code', 'ecue_nom',
            'session_rattrapage', 'session_libelle',
            'statut', 'statut_display',
            'date_inscription', 'note', 'date_echeance_inscription',
        ]
        read_only_fields = ['id', 'date_inscription']
