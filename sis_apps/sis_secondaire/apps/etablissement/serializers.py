"""Serializers for etablissement (SIS Secondaire)."""

from rest_framework import serializers

from .models import AnneeScolaire, Etablissement, Periode


class EtablissementSerializer(serializers.ModelSerializer):
    """Serializer pour les établissements."""

    type_display = serializers.CharField(source="get_type_display", read_only=True)
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
            "uai",
            "adresse",
            "code_postal",
            "ville",
            "pays",
            "telephone",
            "email",
            "site_web",
            "logo",
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
