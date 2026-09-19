"""Serializers for mobilite internationale (SIS Supérieur)."""

from rest_framework import serializers

from .models import AccordEtudes, CandidatureMobilite, ProgrammeMobilite


class ProgrammeMobiliteListSerializer(serializers.ModelSerializer):
    """Serializer léger pour les programmes."""

    type_display = serializers.CharField(source="get_type_display", read_only=True)
    formation_nom = serializers.CharField(source="formation.nom", read_only=True)
    nb_candidatures = serializers.SerializerMethodField()
    places_restantes = serializers.SerializerMethodField()

    class Meta:
        model = ProgrammeMobilite
        fields = [
            "id",
            "formation",
            "formation_nom",
            "nom",
            "type",
            "type_display",
            "universite_accueil",
            "pays",
            "duree_mois",
            "nb_places",
            "nb_candidatures",
            "places_restantes",
            "date_limite_candidature",
            "actif",
        ]

    def get_nb_candidatures(self, obj):
        return obj.candidatures.count()

    def get_places_restantes(self, obj):
        acceptees = obj.candidatures.filter(statut="acceptee").count()
        return obj.nb_places - acceptees


class ProgrammeMobiliteDetailSerializer(serializers.ModelSerializer):
    """Serializer complet pour un programme."""

    type_display = serializers.CharField(source="get_type_display", read_only=True)
    formation_nom = serializers.CharField(source="formation.nom", read_only=True)
    annee_libelle = serializers.CharField(
        source="annee_universitaire.libelle", read_only=True
    )

    class Meta:
        model = ProgrammeMobilite
        fields = [
            "id",
            "formation",
            "formation_nom",
            "nom",
            "type",
            "type_display",
            "universite_accueil",
            "pays",
            "duree_mois",
            "nb_places",
            "langue_requise",
            "niveau_langue",
            "description",
            "date_limite_candidature",
            "annee_universitaire",
            "annee_libelle",
            "actif",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class CandidatureMobiliteListSerializer(serializers.ModelSerializer):
    """Serializer léger pour les candidatures."""

    etudiant_matricule = serializers.CharField(
        source="etudiant.matricule", read_only=True
    )
    etudiant_nom = serializers.CharField(
        source="etudiant.user.get_full_name", read_only=True
    )
    programme_nom = serializers.CharField(source="programme.nom", read_only=True)
    universite = serializers.CharField(
        source="programme.universite_accueil", read_only=True
    )
    statut_display = serializers.CharField(source="get_statut_display", read_only=True)

    class Meta:
        model = CandidatureMobilite
        fields = [
            "id",
            "etudiant",
            "etudiant_matricule",
            "etudiant_nom",
            "programme",
            "programme_nom",
            "universite",
            "moyenne_ponderee",
            "statut",
            "statut_display",
            "date_soumission",
        ]


class CandidatureMobiliteDetailSerializer(serializers.ModelSerializer):
    """Serializer complet pour une candidature."""

    etudiant_matricule = serializers.CharField(
        source="etudiant.matricule", read_only=True
    )
    etudiant_nom = serializers.CharField(
        source="etudiant.user.get_full_name", read_only=True
    )
    programme_nom = serializers.CharField(source="programme.nom", read_only=True)
    statut_display = serializers.CharField(source="get_statut_display", read_only=True)
    decision_par_nom = serializers.CharField(
        source="decision_par.get_full_name", read_only=True
    )

    class Meta:
        model = CandidatureMobilite
        fields = [
            "id",
            "etudiant",
            "etudiant_matricule",
            "etudiant_nom",
            "programme",
            "programme_nom",
            "lettre_motivation",
            "cv",
            "releve_notes",
            "certificat_langue",
            "projet_personnel",
            "moyenne_ponderee",
            "statut",
            "statut_display",
            "date_soumission",
            "decision_par",
            "decision_par_nom",
            "motif_refus",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class AccordEtudesSerializer(serializers.ModelSerializer):
    """Serializer pour les accords d'études."""

    etudiant_nom = serializers.CharField(
        source="candidature.etudiant.user.get_full_name", read_only=True
    )
    programme_nom = serializers.CharField(
        source="candidature.programme.nom", read_only=True
    )
    statut_display = serializers.CharField(source="get_statut_display", read_only=True)

    class Meta:
        model = AccordEtudes
        fields = [
            "id",
            "candidature",
            "etudiant_nom",
            "programme_nom",
            "pdf_signe",
            "statut",
            "statut_display",
            "date_validation_origine",
            "date_validation_accueil",
        ]
        read_only_fields = ["id"]
