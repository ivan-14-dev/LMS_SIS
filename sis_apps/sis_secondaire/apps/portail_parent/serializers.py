"""Serializers for portail parent (SIS Secondaire)."""
from rest_framework import serializers


class TableauBordParentSerializer(serializers.Serializer):
    """Serializer pour le tableau de bord parent."""
    enfants = serializers.ListField()
    notifications = serializers.ListField()
    factures_impayees = serializers.ListField()


class EnfantSerializer(serializers.Serializer):
    """Serializer pour les informations d'un enfant."""
    id = serializers.IntegerField()
    matricule = serializers.CharField()
    nom = serializers.CharField()
    classe = serializers.CharField()
    moyenne = serializers.DecimalField(max_digits=5, decimal_places=2, allow_null=True)
    absences = serializers.IntegerField()
    retards = serializers.IntegerField()
