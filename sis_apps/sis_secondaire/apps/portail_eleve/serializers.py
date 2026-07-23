"""Serializers for portail élève (SIS Secondaire)."""
from rest_framework import serializers


class TableauBordEleveSerializer(serializers.Serializer):
    """Serializer pour le tableau de bord élève."""
    eleve = serializers.DictField()
    classe = serializers.DictField()
    statistiques = serializers.DictField()
    prochains_cours = serializers.ListField()
    notes_recentes = serializers.ListField()


class ProfilEleveSerializer(serializers.Serializer):
    """Serializer pour le profil élève."""
    matricule = serializers.CharField()
    nom = serializers.CharField()
    classe = serializers.CharField()
    niveau = serializers.CharField()
    moyenne = serializers.DecimalField(max_digits=5, decimal_places=2, allow_null=True)
    rang = serializers.IntegerField(allow_null=True)
