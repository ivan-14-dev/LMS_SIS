"""Compatibility serializers for superior administrative enrollment workflows."""

from apps.etudiants.serializers import InscriptionAdministrativeSerializer


class InscriptionSerializer(InscriptionAdministrativeSerializer):
    """Backward-compatible serializer aligned with active enrollment models."""

