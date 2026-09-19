"""Serializers for portail enseignant (SIS Secondaire)."""

from rest_framework import serializers


class TableauBordEnseignantSerializer(serializers.Serializer):
    """Serializer pour le tableau de bord enseignant."""

    enseignant = serializers.DictField()
    classes = serializers.ListField()
    prochains_cours = serializers.ListField()
    notes_a_saisir = serializers.IntegerField()
    absences_a_signaler = serializers.IntegerField()


class ClasseEnseignantSerializer(serializers.Serializer):
    """Serializer pour les classes de l'enseignant."""

    classe_id = serializers.IntegerField()
    classe_nom = serializers.CharField()
    matiere = serializers.CharField()
    nb_eleves = serializers.IntegerField()
    est_pp = serializers.BooleanField()  # Professeur principal
