"""Serializers for releves (SIS Supérieur)."""

from apps.etudiants.models import AffectationECUEIndividuelle
from rest_framework import serializers

from .models import Attestation, ReleveNotes, Transcript


class ReleveNotesListSerializer(serializers.ModelSerializer):
    """Serializer léger pour les relevés."""

    etudiant_matricule = serializers.CharField(
        source="etudiant.matricule", read_only=True
    )
    etudiant_nom = serializers.CharField(
        source="etudiant.user.get_full_name", read_only=True
    )
    semestre_nom = serializers.CharField(source="semestre.__str__", read_only=True)

    class Meta:
        model = ReleveNotes
        fields = [
            "id",
            "etudiant",
            "etudiant_matricule",
            "etudiant_nom",
            "semestre",
            "semestre_nom",
            "moyenne_generale",
            "mention",
            "credits_valides",
            "credits_total",
            "classement",
            "effectif",
            "date_emission",
            "signe",
            "numero_serie",
        ]


class ReleveNotesDetailSerializer(serializers.ModelSerializer):
    """Serializer complet pour un relevé."""

    etudiant_matricule = serializers.CharField(
        source="etudiant.matricule", read_only=True
    )
    etudiant_nom = serializers.CharField(
        source="etudiant.user.get_full_name", read_only=True
    )
    semestre_nom = serializers.CharField(source="semestre.__str__", read_only=True)
    signe_par_nom = serializers.CharField(
        source="signe_par.get_full_name", read_only=True
    )
    nb_matieres_individualisees = serializers.SerializerMethodField()
    matieres_individuelles = serializers.SerializerMethodField()

    class Meta:
        model = ReleveNotes
        fields = [
            "id",
            "etudiant",
            "etudiant_matricule",
            "etudiant_nom",
            "semestre",
            "semestre_nom",
            "pdf_path",
            "moyenne_generale",
            "mention",
            "credits_total",
            "credits_valides",
            "nb_matieres_individualisees",
            "matieres_individuelles",
            "classement",
            "effectif",
            "date_emission",
            "signe",
            "date_signature",
            "signe_par",
            "signe_par_nom",
            "numero_serie",
            "qr_verification",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def _affectations(self, obj):
        return (
            AffectationECUEIndividuelle.objects.filter(
                inscription_admin__etudiant=obj.etudiant,
                inscription_admin__annee_universitaire=obj.semestre.annee_universitaire,
                semestre_cible=obj.semestre,
            )
            .select_related("ecue__ue", "semestre_cible")
            .order_by("ecue__ue__code", "ecue__code")
        )

    def get_nb_matieres_individualisees(self, obj):
        return self._affectations(obj).count()

    def get_matieres_individuelles(self, obj):
        return [
            {
                "id": affectation.id,
                "ecue": affectation.ecue_id,
                "ecue_code": affectation.ecue.code,
                "ecue_nom": affectation.ecue.nom,
                "ue_code": affectation.ecue.ue.code,
                "ue_nom": affectation.ecue.ue.nom,
                "semestre_cible": affectation.semestre_cible_id,
                "semestre_cible_libelle": str(affectation.semestre_cible),
                "source_semestre": str(affectation.ecue.ue.semestre),
                "obligatoire": affectation.obligatoire,
            }
            for affectation in self._affectations(obj)
        ]


class TranscriptListSerializer(serializers.ModelSerializer):
    """Serializer léger pour les transcripts."""

    etudiant_matricule = serializers.CharField(
        source="etudiant.matricule", read_only=True
    )
    etudiant_nom = serializers.CharField(
        source="etudiant.user.get_full_name", read_only=True
    )
    nb_annees = serializers.SerializerMethodField()

    class Meta:
        model = Transcript
        fields = [
            "id",
            "etudiant",
            "etudiant_matricule",
            "etudiant_nom",
            "nb_annees",
            "credits_total",
            "credits_valides",
            "moyenne_ponderee",
            "mention_finale",
            "diplome_prepare",
            "date_emission",
            "numero_serie",
        ]

    def get_nb_annees(self, obj):
        return obj.annees.count()


class TranscriptDetailSerializer(serializers.ModelSerializer):
    """Serializer complet pour un transcript."""

    etudiant_matricule = serializers.CharField(
        source="etudiant.matricule", read_only=True
    )
    etudiant_nom = serializers.CharField(
        source="etudiant.user.get_full_name", read_only=True
    )
    signe_par_nom = serializers.CharField(
        source="signe_par.get_full_name", read_only=True
    )
    annees_list = serializers.SerializerMethodField()

    class Meta:
        model = Transcript
        fields = [
            "id",
            "etudiant",
            "etudiant_matricule",
            "etudiant_nom",
            "annees",
            "annees_list",
            "pdf_path",
            "credits_total",
            "credits_valides",
            "moyenne_ponderee",
            "mention_finale",
            "diplome_prepare",
            "date_emission",
            "numero_serie",
            "signe_par",
            "signe_par_nom",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_annees_list(self, obj):
        return [{"id": a.id, "libelle": a.libelle} for a in obj.annees.all()]


class AttestationSerializer(serializers.ModelSerializer):
    """Serializer pour les attestations."""

    etudiant_matricule = serializers.CharField(
        source="etudiant.matricule", read_only=True
    )
    etudiant_nom = serializers.CharField(
        source="etudiant.user.get_full_name", read_only=True
    )
    type_display = serializers.CharField(source="get_type_display", read_only=True)
    signe_par_nom = serializers.CharField(
        source="signe_par.get_full_name", read_only=True
    )

    class Meta:
        model = Attestation
        fields = [
            "id",
            "etudiant",
            "etudiant_matricule",
            "etudiant_nom",
            "type",
            "type_display",
            "pdf_path",
            "date_emission",
            "date_validite",
            "numero",
            "signe_par",
            "signe_par_nom",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]
