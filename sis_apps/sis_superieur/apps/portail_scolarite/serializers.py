"""Serializers for portail scolarité (SIS Supérieur)."""
from rest_framework import serializers


class TableauBordScolariteSerializer(serializers.Serializer):
    """Serializer pour le tableau de bord scolarité."""
    statistiques = serializers.DictField()
    inscriptions_recentes = serializers.ListField()
    dossiers_en_attente = serializers.ListField()
    alertes = serializers.ListField()


class StatistiquesFormationSerializer(serializers.Serializer):
    """Statistiques par formation."""
    formation_id = serializers.IntegerField()
    formation_nom = serializers.CharField()
    nb_inscrits = serializers.IntegerField()
    nb_admis = serializers.IntegerField()
    taux_reussite = serializers.FloatField()
    moyenne_generale = serializers.DecimalField(max_digits=5, decimal_places=2, allow_null=True)
