"""Serializers for etablissement (SIS Secondaire)."""

from rest_framework import serializers
from sis_common.establishments import (
    FEATURE_LABELS,
    LIVE_PROVIDER_LABELS,
    default_establishment_features,
    default_live_configuration,
)

from .models import AnneeScolaire, Etablissement, Periode


class EtablissementSerializer(serializers.ModelSerializer):
    """Serializer pour les établissements."""

    type_display = serializers.CharField(source="get_type_display", read_only=True)
    type_options = serializers.SerializerMethodField()
    feature_options = serializers.SerializerMethodField()
    live_provider_options = serializers.SerializerMethodField()
    systeme_periodes_display = serializers.CharField(
        source="get_systeme_periodes_display", read_only=True
    )
    nb_annees = serializers.SerializerMethodField()

    class Meta:
        model = Etablissement
        fields = [
            "id",
            "nom",
            "type",
            "type_display",
            "type_personnalise",
            "type_options",
            "uai",
            "adresse",
            "code_postal",
            "ville",
            "pays",
            "telephone",
            "email",
            "site_web",
            "logo",
            "couleur_primaire",
            "couleur_secondaire",
            "fuseau_horaire",
            "fonctionnalites",
            "feature_options",
            "configuration_visio",
            "live_provider_options",
            "devise",
            "ministere_tutelle",
            "systeme_periodes",
            "systeme_periodes_display",
            "nb_annees",
            "actif",
            "date_creation",
        ]
        read_only_fields = ["id", "date_creation"]

    def get_nb_annees(self, obj):
        return obj.annees_scolaires.count()

    def get_type_options(self, obj):
        return [{"value": value, "label": label} for value, label in obj.TYPE_CHOICES]

    def get_feature_options(self, obj):
        return [
            {"value": value, "label": label} for value, label in FEATURE_LABELS.items()
        ]

    def get_live_provider_options(self, obj):
        return [
            {"value": value, "label": label}
            for value, label in LIVE_PROVIDER_LABELS.items()
        ]

    def validate(self, attrs):
        institution_type = attrs.get("type", getattr(self.instance, "type", None))
        custom_type = attrs.get(
            "type_personnalise", getattr(self.instance, "type_personnalise", "")
        )
        if institution_type == "autre" and not custom_type.strip():
            raise serializers.ValidationError(
                {"type_personnalise": "Précisez le type de cet établissement."}
            )
        return attrs

    def validate_fonctionnalites(self, value):
        current = getattr(self.instance, "fonctionnalites", {})
        return {**default_establishment_features(), **current, **value}

    def validate_configuration_visio(self, value):
        current = getattr(self.instance, "configuration_visio", {})
        return {**default_live_configuration(), **current, **value}


class AnneeScolaireSerializer(serializers.ModelSerializer):
    """Serializer pour les années scolaires."""

    nb_periodes = serializers.SerializerMethodField()

    class Meta:
        model = AnneeScolaire
        fields = [
            "id",
            "etablissement",
            "libelle",
            "date_debut",
            "date_fin",
            "en_cours",
            "cloturee",
            "nb_periodes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_nb_periodes(self, obj):
        return obj.periodes.count()


class PeriodeSerializer(serializers.ModelSerializer):
    """Serializer pour les périodes."""

    annee_libelle = serializers.CharField(
        source="annee_scolaire.libelle", read_only=True
    )
    type_display = serializers.CharField(source="get_type_display", read_only=True)

    class Meta:
        model = Periode
        fields = [
            "id",
            "annee_scolaire",
            "annee_libelle",
            "numero",
            "type",
            "type_display",
            "nom",
            "date_debut",
            "date_fin",
            "cloture",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]
