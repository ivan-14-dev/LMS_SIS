"""Serializers for etablissement (SIS Secondaire)."""

from rest_framework import serializers
from sis_common.academic_configuration import (
    academic_configuration_schema,
    catalog_label,
    catalog_options,
    merge_academic_configuration,
)
from sis_common.establishments import (
    FEATURE_LABELS,
    LIVE_PROVIDER_LABELS,
    default_establishment_features,
    default_live_configuration,
)

from .models import AnneeScolaire, Etablissement, Niveau, Periode


class EtablissementSerializer(serializers.ModelSerializer):
    """Serializer pour les établissements."""

    type_display = serializers.SerializerMethodField()
    type_options = serializers.SerializerMethodField()
    feature_options = serializers.SerializerMethodField()
    live_provider_options = serializers.SerializerMethodField()
    configuration_schema = serializers.SerializerMethodField()
    systeme_periodes_display = serializers.SerializerMethodField()
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
            "configuration_academique",
            "configuration_schema",
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
        return [
            {"value": item["code"], "label": item["label"]}
            for item in catalog_options(
                obj.configuration_academique,
                "institution_types",
                obj.TYPE_CHOICES,
            )
        ]

    def get_type_display(self, obj):
        return catalog_label(
            obj.configuration_academique,
            "institution_types",
            obj.type,
            obj.TYPE_CHOICES,
        )

    def get_systeme_periodes_display(self, obj):
        fallback = (
            ("trimestre", "Trimestre"),
            ("semestre", "Semestre"),
            ("quadrimestre", "Quadrimestre"),
        )
        return catalog_label(
            obj.configuration_academique,
            "period_types",
            obj.systeme_periodes,
            fallback,
        )

    def get_feature_options(self, obj):
        return [{"value": value, "label": label} for value, label in FEATURE_LABELS.items()]

    def get_live_provider_options(self, obj):
        return [{"value": value, "label": label} for value, label in LIVE_PROVIDER_LABELS.items()]

    def get_configuration_schema(self, obj):
        return academic_configuration_schema("secondaire")

    def validate(self, attrs):
        institution_type = attrs.get("type", getattr(self.instance, "type", None))
        custom_type = attrs.get("type_personnalise", getattr(self.instance, "type_personnalise", ""))
        if institution_type == "autre" and not custom_type.strip():
            raise serializers.ValidationError({"type_personnalise": "Précisez le type de cet établissement."})
        return attrs

    def validate_fonctionnalites(self, value):
        current = getattr(self.instance, "fonctionnalites", {})
        return {**default_establishment_features(), **current, **value}

    def validate_configuration_visio(self, value):
        current = getattr(self.instance, "configuration_visio", {})
        return {**default_live_configuration(), **current, **value}

    def validate_configuration_academique(self, value):
        current = getattr(self.instance, "configuration_academique", {})
        return merge_academic_configuration(current, value)


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
        read_only_fields = ["id", "etablissement", "created_at", "updated_at"]

    def get_nb_periodes(self, obj):
        return obj.periodes.count()


class PeriodeSerializer(serializers.ModelSerializer):
    """Serializer pour les périodes."""

    annee_libelle = serializers.CharField(source="annee_scolaire.libelle", read_only=True)
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
            "libelle",
            "date_debut",
            "date_fin",
            "cloturee",
        ]
        read_only_fields = ["id"]

    def validate_annee_scolaire(self, value):
        request = self.context.get("request")
        if request and value.etablissement_id != request.tenant.id:
            raise serializers.ValidationError("Cette année n'appartient pas à l'établissement courant.")
        return value


class NiveauSerializer(serializers.ModelSerializer):
    class Meta:
        model = Niveau
        fields = ["id", "etablissement", "code", "libelle", "ordre", "cycle"]
        read_only_fields = ["id", "etablissement"]
