"""Serializers for diplomes (SIS Supérieur)."""

from rest_framework import serializers

from .models import CessionDiplome, Diplome


class DiplomeSerializer(serializers.ModelSerializer):
    """Serializer pour les types de diplômes."""

    formation_nom = serializers.CharField(source="formation.nom", read_only=True)
    type_display = serializers.CharField(source="get_type_display", read_only=True)
    nb_cessions = serializers.SerializerMethodField()

    class Meta:
        model = Diplome
        fields = [
            "id",
            "formation",
            "formation_nom",
            "type",
            "type_display",
            "nom",
            "niveau_grade",
            "code_rncp",
            "credits_ects",
            "conditions",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_nb_cessions(self, obj):
        return obj.cessions.count()


class CessionDiplomeListSerializer(serializers.ModelSerializer):
    """Serializer léger pour les listes de cessions."""

    etudiant_matricule = serializers.CharField(
        source="etudiant.matricule", read_only=True
    )
    etudiant_nom = serializers.CharField(
        source="etudiant.user.get_full_name", read_only=True
    )
    diplome_nom = serializers.CharField(source="diplome.nom", read_only=True)
    annee_libelle = serializers.CharField(
        source="annee_universitaire.libelle", read_only=True
    )

    class Meta:
        model = CessionDiplome
        fields = [
            "id",
            "etudiant",
            "etudiant_matricule",
            "etudiant_nom",
            "diplome",
            "diplome_nom",
            "annee_universitaire",
            "annee_libelle",
            "date_obtention",
            "mention",
            "moyenne_finale",
        ]


class CessionDiplomeDetailSerializer(serializers.ModelSerializer):
    """Serializer complet pour une cession de diplôme."""

    etudiant_matricule = serializers.CharField(
        source="etudiant.matricule", read_only=True
    )
    etudiant_nom = serializers.CharField(
        source="etudiant.user.get_full_name", read_only=True
    )
    diplome_nom = serializers.CharField(source="diplome.nom", read_only=True)
    annee_libelle = serializers.CharField(
        source="annee_universitaire.libelle", read_only=True
    )
    signe_par_nom = serializers.CharField(
        source="signe_par.get_full_name", read_only=True
    )

    class Meta:
        model = CessionDiplome
        fields = [
            "id",
            "etudiant",
            "etudiant_matricule",
            "etudiant_nom",
            "diplome",
            "diplome_nom",
            "annee_universitaire",
            "annee_libelle",
            "date_obtention",
            "mention",
            "moyenne_finale",
            "numero_serie",
            "pdf_path",
            "signe_par",
            "signe_par_nom",
            "date_signature",
            "qr_verification",
            "created_at",
        ]
        read_only_fields = ["id", "numero_serie", "created_at"]
