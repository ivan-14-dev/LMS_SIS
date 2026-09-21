"""Compatibility serializers for secondary evaluations."""

from apps.notes.serializers import EvaluationDetailSerializer


class EvaluationSerializer(EvaluationDetailSerializer):
    """Backward-compatible serializer aligned with active evaluation models."""
