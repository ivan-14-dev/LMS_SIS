"""Serializers for diplomes (SIS Supérieur)."""

from rest_framework import serializers

from .models import CessionDiplome, Diplome
from .services import has_issuance_prerequisite


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
            "nb_cessions",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_nb_cessions(self, obj):
        return obj.cessions.count()


class CessionDiplomeListSerializer(serializers.ModelSerializer):
    """Serializer léger pour les listes de cessions."""

    etudiant_matricule = serializers.CharField(source="etudiant.matricule", read_only=True)
    etudiant_nom = serializers.CharField(source="etudiant.user.get_full_name", read_only=True)
    diplome_nom = serializers.CharField(source="diplome.nom", read_only=True)
    annee_libelle = serializers.CharField(source="annee_universitaire.libelle", read_only=True)

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
            "date_signature",
            "date_revocation",
        ]


class CessionDiplomeDetailSerializer(serializers.ModelSerializer):
    """Serializer complet pour une cession de diplôme."""

    etudiant_matricule = serializers.CharField(source="etudiant.matricule", read_only=True)
    etudiant_nom = serializers.CharField(source="etudiant.user.get_full_name", read_only=True)
    diplome_nom = serializers.CharField(source="diplome.nom", read_only=True)
    annee_libelle = serializers.CharField(source="annee_universitaire.libelle", read_only=True)
    signe_par_nom = serializers.CharField(source="signe_par.get_full_name", read_only=True)

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
            "date_revocation",
            "qr_verification",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "numero_serie",
            "signe_par",
            "date_signature",
            "date_revocation",
            "qr_verification",
            "created_at",
        ]

    def validate(self, attrs):
        identity_fields = ("etudiant", "diplome", "annee_universitaire", "date_obtention")
        if self.instance and self.instance.date_signature is not None:
            if any(
                field in attrs and attrs[field] != getattr(self.instance, field)
                for field in identity_fields
            ):
                raise serializers.ValidationError(
                    "Le titulaire et le diplôme d'une délivrance signée ne peuvent pas être modifiés."
                )
        if self.instance is None or any(field in attrs for field in identity_fields):
            values = {
                field: attrs.get(field, getattr(self.instance, field, None))
                for field in identity_fields
            }
            if not has_issuance_prerequisite(
                **values,
                tenant=getattr(self.context.get("request"), "tenant", None),
            ):
                raise serializers.ValidationError(
                    "Une inscription validée et une admission par le jury final clôturé sont requises."
                )
        return attrs


class AlumniRevisionSerializer(serializers.Serializer):
    revision = serializers.IntegerField(min_value=0)

    def to_internal_value(self, data):
        unknown = set(data) - set(self.fields)
        if unknown:
            raise serializers.ValidationError(
                {field: "Champ non autorisé." for field in sorted(unknown)}
            )
        return super().to_internal_value(data)


class AlumniOptInSerializer(AlumniRevisionSerializer):
    consentement = serializers.BooleanField()

    def validate_consentement(self, value):
        if value is not True:
            raise serializers.ValidationError("Un accord explicite est requis.")
        return value
