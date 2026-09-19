"""Serializers for formations (SIS Supérieur)."""

from rest_framework import serializers

from .models import Formation, MaquetteFormation, Parcours


class FormationListSerializer(serializers.ModelSerializer):
    """Serializer léger pour les listes de formations."""

    type_display = serializers.CharField(source="get_type_display", read_only=True)
    niveau_display = serializers.CharField(source="get_niveau_display", read_only=True)
    departement_nom = serializers.CharField(source="departement.nom", read_only=True)
    responsable_nom = serializers.CharField(
        source="responsable.get_full_name", read_only=True
    )

    class Meta:
        model = Formation
        fields = [
            "id",
            "code",
            "nom",
            "type",
            "type_display",
            "niveau",
            "niveau_display",
            "duree_annees",
            "credits_total",
            "departement",
            "departement_nom",
            "responsable",
            "responsable_nom",
            "actif",
        ]


class FormationDetailSerializer(serializers.ModelSerializer):
    """Serializer complet pour une formation."""

    type_display = serializers.CharField(source="get_type_display", read_only=True)
    niveau_display = serializers.CharField(source="get_niveau_display", read_only=True)
    regime_display = serializers.CharField(source="get_regime_display", read_only=True)
    departement_nom = serializers.CharField(source="departement.nom", read_only=True)
    responsable_nom = serializers.CharField(
        source="responsable.get_full_name", read_only=True
    )
    nb_parcours = serializers.SerializerMethodField()

    class Meta:
        model = Formation
        fields = [
            "id",
            "code",
            "nom",
            "type",
            "type_display",
            "niveau",
            "niveau_display",
            "duree_annees",
            "nb_semestres",
            "credits_total",
            "departement",
            "departement_nom",
            "ecole_doctorale",
            "responsable",
            "responsable_nom",
            "regime",
            "regime_display",
            "accreditations",
            "date_accreditation",
            "date_fin_accreditation",
            "description",
            "objectifs",
            "debouches",
            "conditions_admission",
            "actif",
            "nb_parcours",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_nb_parcours(self, obj):
        return obj.parcours.count()


class ParcoursSerializer(serializers.ModelSerializer):
    """Serializer pour les parcours."""

    formation_nom = serializers.CharField(source="formation.nom", read_only=True)
    formation_code = serializers.CharField(source="formation.code", read_only=True)

    class Meta:
        model = Parcours
        fields = [
            "id",
            "formation",
            "formation_nom",
            "formation_code",
            "code",
            "nom",
            "specialisation",
            "description",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class MaquetteFormationSerializer(serializers.ModelSerializer):
    """Serializer pour les maquettes de formation."""

    formation_nom = serializers.CharField(source="formation.nom", read_only=True)
    annee_libelle = serializers.CharField(
        source="annee_universitaire.libelle", read_only=True
    )

    class Meta:
        model = MaquetteFormation
        fields = [
            "id",
            "formation",
            "formation_nom",
            "annee_universitaire",
            "annee_libelle",
            "structure",
            "statut",
        ]
        read_only_fields = ["id"]
