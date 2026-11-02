"""Serializers for salles (SIS Secondaire)."""

from rest_framework import serializers

from sis_common.serializers import TenantBoundSerializerMixin

from .models import Salle


class SalleListSerializer(serializers.ModelSerializer):
    """Serializer léger pour les listes de salles."""

    type_display = serializers.CharField(source="get_type_display", read_only=True)

    class Meta:
        model = Salle
        fields = [
            "id",
            "code",
            "nom",
            "batiment",
            "etage",
            "type",
            "type_display",
            "capacite",
            "accessible_pm",
        ]


class SalleDetailSerializer(TenantBoundSerializerMixin, serializers.ModelSerializer):
    """Serializer complet pour une salle."""

    type_display = serializers.CharField(source="get_type_display", read_only=True)

    class Meta:
        model = Salle
        fields = [
            "id",
            "etablissement",
            "code",
            "nom",
            "batiment",
            "etage",
            "capacite",
            "type",
            "type_display",
            "equipements",
            "accessible_pm",
            "surface_m2",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "etablissement", "created_at", "updated_at"]
