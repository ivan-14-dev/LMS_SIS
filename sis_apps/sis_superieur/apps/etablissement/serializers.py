"""Serializers for etablissement (SIS Supérieur)."""

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

from .models import AnneeUniversitaire, Semestre, Universite


class UniversiteSerializer(serializers.ModelSerializer):
    """Serializer pour les universités."""

    type_display = serializers.SerializerMethodField()
    type_options = serializers.SerializerMethodField()
    feature_options = serializers.SerializerMethodField()
    live_provider_options = serializers.SerializerMethodField()
    configuration_schema = serializers.SerializerMethodField()
    nb_facultes = serializers.SerializerMethodField()

    class Meta:
        model = Universite
        fields = [
            "id",
            "nom",
            "sigle",
            "type",
            "type_display",
            "type_personnalise",
            "type_options",
            "ministere_tutelle",
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
            "systeme_notation",
            "credits_annee",
            "accreditations",
            "conventions_internationales",
            "nb_facultes",
            "actif",
            "date_creation",
        ]
        read_only_fields = ["id", "date_creation"]

    def get_nb_facultes(self, obj):
        return obj.facultes.count() if hasattr(obj, "facultes") else 0

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

    def get_feature_options(self, obj):
        return [{"value": value, "label": label} for value, label in FEATURE_LABELS.items()]

    def get_live_provider_options(self, obj):
        return [{"value": value, "label": label} for value, label in LIVE_PROVIDER_LABELS.items()]

    def get_configuration_schema(self, obj):
        return academic_configuration_schema("superieur")

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


class AnneeUniversitaireSerializer(serializers.ModelSerializer):
    """Serializer pour les années universitaires."""

    nb_semestres = serializers.SerializerMethodField()

    class Meta:
        model = AnneeUniversitaire
        fields = [
            "id",
            "universite",
            "libelle",
            "date_debut",
            "date_fin",
            "en_cours",
            "cloturee",
            "nb_semestres",
            "created_at",
        ]
        read_only_fields = ["id", "universite", "created_at"]

    def get_nb_semestres(self, obj):
        return obj.semestres.count()


class SemestreSerializer(serializers.ModelSerializer):
    """Serializer pour les semestres."""

    annee_libelle = serializers.CharField(source="annee_universitaire.libelle", read_only=True)
    type_display = serializers.CharField(source="get_type_display", read_only=True)
    libelle = serializers.SerializerMethodField()

    class Meta:
        model = Semestre
        fields = [
            "id",
            "annee_universitaire",
            "annee_libelle",
            "numero",
            "type",
            "type_display",
            "libelle",
            "date_debut",
            "date_fin",
            "cloture",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_libelle(self, obj):
        return str(obj)

    def validate_annee_universitaire(self, value):
        request = self.context.get("request")
        if request and value.universite_id != request.tenant.id:
            raise serializers.ValidationError("Cette année n'appartient pas à l'établissement courant.")
        return value
