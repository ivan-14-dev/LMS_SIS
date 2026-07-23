"""Serializers for portail doyen (SIS Supérieur)."""
from rest_framework import serializers


class TableauBordDoyenSerializer(serializers.Serializer):
    """Serializer pour le tableau de bord du doyen."""
    faculte = serializers.DictField()
    statistiques = serializers.DictField()
    departements = serializers.ListField()
    alertes = serializers.ListField()


class StatistiquesFaculteSerializer(serializers.Serializer):
    """Statistiques de la faculté."""
    nb_etudiants = serializers.IntegerField()
    nb_enseignants = serializers.IntegerField()
    nb_formations = serializers.IntegerField()
    taux_reussite_global = serializers.FloatField()
    nb_theses_en_cours = serializers.IntegerField()
    nb_laboratoires = serializers.IntegerField()
