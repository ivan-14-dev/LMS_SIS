"""Serializers for cantine (SIS Secondaire)."""

from rest_framework import serializers

from .models import InscriptionCantine, Menu, PresenceCantine


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


class InscriptionCantineSerializer(serializers.ModelSerializer):
    """Serializer pour les inscriptions cantine."""

    eleve_matricule = serializers.CharField(source="eleve.matricule", read_only=True)
    eleve_nom = serializers.CharField(source="eleve.user.get_full_name", read_only=True)
    eleve_classe = serializers.CharField(source="eleve.classe.nom", read_only=True)
    forfait_display = serializers.CharField(
        source="get_forfait_display", read_only=True
    )
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


class PointageCantineSerializer(serializers.Serializer):
    """Serializer pour le pointage en masse."""

    eleve_id = serializers.IntegerField()
    present = serializers.BooleanField(default=True)
