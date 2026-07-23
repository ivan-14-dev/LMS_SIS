"""Serializers for portail enseignant (SIS Supérieur)."""
from rest_framework import serializers


class TableauBordEnseignantSerializer(serializers.Serializer):
    """Serializer pour le tableau de bord enseignant."""
    enseignant = serializers.DictField()
    cours_semestre = serializers.ListField()
    notes_a_saisir = serializers.IntegerField()
    prochains_cours = serializers.ListField()
    statistiques = serializers.DictField()


class CoursEnseignantSerializer(serializers.Serializer):
    """Serializer pour les cours de l'enseignant."""
    ecue_id = serializers.IntegerField()
    ecue_nom = serializers.CharField()
    ue_nom = serializers.CharField()
    formation = serializers.CharField()
    nb_etudiants = serializers.IntegerField()
    notes_saisies = serializers.IntegerField()
    heures_prevues = serializers.IntegerField()
    heures_effectuees = serializers.IntegerField()
