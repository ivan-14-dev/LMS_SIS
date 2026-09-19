"""Serializers for evaluations (SIS Secondaire).

Note: Ce module complète le module notes avec des évaluations spécifiques
(compétences, projets, etc.).
"""

from apps.notes.models import Note
from rest_framework import serializers


class EvaluationSerializer(serializers.ModelSerializer):
    """Serializer pour les évaluations."""

    eleve_matricule = serializers.CharField(source="eleve.matricule", read_only=True)
    eleve_nom = serializers.CharField(source="eleve.user.get_full_name", read_only=True)
    matiere_nom = serializers.CharField(source="matiere.nom", read_only=True)

    class Meta:
        model = Note
        fields = [
            "id",
            "eleve",
            "eleve_matricule",
            "eleve_nom",
            "matiere",
            "matiere_nom",
            "type_evaluation",
            "note",
            "coefficient",
            "appreciation",
            "date",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]
