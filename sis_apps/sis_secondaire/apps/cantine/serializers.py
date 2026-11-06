"""Serializers for cantine (SIS Secondaire)."""

from apps.eleves.models import Eleve
from django.db.models import Q
from rest_framework import serializers

from sis_common.serializers import DateRangeSerializerMixin

from .models import InscriptionCantine, Menu, PresenceCantine


def _has_valid_inscription(eleve_id, menu, tenant):
    if tenant is None:
        return False
    return InscriptionCantine.objects.filter(
        eleve_id=eleve_id,
        eleve__etablissement_id=tenant.pk,
        actif=True,
        date_debut__lte=menu.date,
    ).filter(Q(date_fin__isnull=True) | Q(date_fin__gte=menu.date)).exists()


class MenuSerializer(serializers.ModelSerializer):
    """Serializer pour les menus."""

    regime_display = serializers.SerializerMethodField()

    class Meta:
        model = Menu
        fields = [
            "id",
            "date",
            "entree",
            "plat",
            "accompagnement",
            "dessert",
            "regime",
            "regime_display",
            "prix",
        ]
        read_only_fields = ["id"]

    def get_regime_display(self, obj):
        return dict(obj._meta.get_field("regime").choices).get(obj.regime, "")


class InscriptionCantineSerializer(DateRangeSerializerMixin, serializers.ModelSerializer):
    """Serializer pour les inscriptions cantine."""

    eleve_matricule = serializers.CharField(source="eleve.matricule", read_only=True)
    eleve_nom = serializers.CharField(source="eleve.user.get_full_name", read_only=True)
    eleve_classe = serializers.CharField(source="eleve.classe_actuelle.nom", read_only=True)
    forfait_display = serializers.CharField(source="get_forfait_display", read_only=True)
    regime_display = serializers.SerializerMethodField()

    class Meta:
        model = InscriptionCantine
        fields = [
            "id",
            "eleve",
            "eleve_matricule",
            "eleve_nom",
            "eleve_classe",
            "forfait",
            "forfait_display",
            "date_debut",
            "date_fin",
            "regime",
            "regime_display",
            "allergies",
            "actif",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_regime_display(self, obj):
        return dict(obj._meta.get_field("regime").choices).get(obj.regime, "")


class PresenceCantineSerializer(serializers.ModelSerializer):
    """Serializer pour les présences cantine."""

    eleve_matricule = serializers.CharField(source="eleve.matricule", read_only=True)
    eleve_nom = serializers.CharField(source="eleve.user.get_full_name", read_only=True)
    menu_date = serializers.DateField(source="menu.date", read_only=True)
    menu_plat = serializers.CharField(source="menu.plat", read_only=True)

    class Meta:
        model = PresenceCantine
        fields = [
            "id",
            "menu",
            "menu_date",
            "menu_plat",
            "eleve",
            "eleve_matricule",
            "eleve_nom",
            "present",
            "heure_pointage",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        menu = attrs.get("menu", getattr(self.instance, "menu", None))
        eleve = attrs.get("eleve", getattr(self.instance, "eleve", None))
        present = attrs.get("present", getattr(self.instance, "present", True))
        tenant = getattr(self.context.get("request"), "tenant", None)
        if eleve is not None and (tenant is None or eleve.etablissement_id != tenant.pk):
            raise serializers.ValidationError({"eleve": "Cet élève appartient à un autre établissement."})
        if present and menu and eleve and not _has_valid_inscription(eleve.pk, menu, tenant):
            raise serializers.ValidationError({"eleve": "Aucune inscription cantine active à cette date."})
        return attrs


class PointageCantineSerializer(serializers.Serializer):
    """Serializer pour le pointage en masse."""

    eleve_id = serializers.IntegerField()
    present = serializers.BooleanField(default=True)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        tenant = getattr(self.context.get("request"), "tenant", None)
        if tenant is None or not Eleve.objects.filter(
            pk=attrs["eleve_id"], etablissement_id=tenant.pk
        ).exists():
            raise serializers.ValidationError({"eleve_id": "Cet élève appartient à un autre établissement."})
        if attrs["present"] and not _has_valid_inscription(attrs["eleve_id"], self.context["menu"], tenant):
            raise serializers.ValidationError({"eleve_id": "Aucune inscription cantine active à cette date."})
        return attrs
