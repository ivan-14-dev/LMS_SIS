"""Serializers for salles (SIS Secondaire)."""

from rest_framework import serializers

from sis_common.serializers import TenantBoundSerializerMixin

from apps.etablissement.models import Etablissement

from .models import Equipement, Salle


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

    def validate_capacite(self, value):
        if value < 1:
            raise serializers.ValidationError("La capacité doit être supérieure à zéro.")
        return value


class EquipementSerializer(TenantBoundSerializerMixin, serializers.ModelSerializer):
    """Inventaire et affectation à une salle du même établissement."""

    etablissement = serializers.PrimaryKeyRelatedField(
        queryset=Etablissement.objects.all(), required=False
    )
    salle = serializers.PrimaryKeyRelatedField(
        queryset=Salle.objects.none(), allow_null=True, required=False
    )
    salle_nom = serializers.CharField(source="salle.nom", read_only=True)

    class Meta:
        model = Equipement
        fields = [
            "id",
            "etablissement",
            "identifiant",
            "nom",
            "salle",
            "salle_nom",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_fields(self):
        fields = super().get_fields()
        tenant = getattr(self.context.get("request"), "tenant", None)
        if tenant is not None:
            fields["salle"].queryset = Salle.objects.filter(etablissement=tenant)
        return fields

    def validate_identifiant(self, value):
        tenant = getattr(self.context.get("request"), "tenant", None)
        if tenant is not None:
            existing = Equipement.objects.filter(etablissement=tenant, identifiant=value)
            if self.instance is not None:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise serializers.ValidationError(
                    "Cet identifiant est déjà utilisé dans cet établissement."
                )
        return value
