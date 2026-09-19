"""Serializers for recherche (SIS Supérieur)."""

from rest_framework import serializers

from .models import Laboratoire, ProductionScientifique, ProjetRecherche, These


class LaboratoireListSerializer(serializers.ModelSerializer):
    """Serializer léger pour les laboratoires."""

    type_display = serializers.CharField(source="get_type_display", read_only=True)
    faculte_nom = serializers.CharField(source="faculte.nom", read_only=True)
    directeur_nom = serializers.CharField(
        source="directeur.user.get_full_name", read_only=True
    )
    nb_projets = serializers.SerializerMethodField()
    nb_theses = serializers.SerializerMethodField()

    class Meta:
        model = Laboratoire
        fields = [
            "id",
            "nom",
            "acronyme",
            "type",
            "type_display",
            "faculte",
            "faculte_nom",
            "directeur_nom",
            "tutelle",
            "nb_projets",
            "nb_theses",
        ]

    def get_nb_projets(self, obj):
        return obj.projets.count()

    def get_nb_theses(self, obj):
        return obj.theses.count()


class LaboratoireDetailSerializer(serializers.ModelSerializer):
    """Serializer complet pour un laboratoire."""

    type_display = serializers.CharField(source="get_type_display", read_only=True)
    faculte_nom = serializers.CharField(source="faculte.nom", read_only=True)
    directeur_nom = serializers.CharField(
        source="directeur.user.get_full_name", read_only=True
    )

    class Meta:
        model = Laboratoire
        fields = [
            "id",
            "nom",
            "acronyme",
            "type",
            "type_display",
            "faculte",
            "faculte_nom",
            "directeur",
            "directeur_nom",
            "tutelle",
            "axes_recherche",
            "numero_rnsr",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class ProjetRechercheListSerializer(serializers.ModelSerializer):
    """Serializer léger pour les projets."""

    laboratoire_nom = serializers.CharField(
        source="laboratoire.acronyme", read_only=True
    )
    responsable_nom = serializers.CharField(
        source="responsable.user.get_full_name", read_only=True
    )
    statut_display = serializers.CharField(source="get_statut_display", read_only=True)

    class Meta:
        model = ProjetRecherche
        fields = [
            "id",
            "titre",
            "acronyme",
            "laboratoire",
            "laboratoire_nom",
            "responsable_nom",
            "financeur",
            "budget",
            "date_debut",
            "date_fin",
            "statut",
            "statut_display",
        ]


class ProjetRechercheDetailSerializer(serializers.ModelSerializer):
    """Serializer complet pour un projet."""

    laboratoire_nom = serializers.CharField(
        source="laboratoire.acronyme", read_only=True
    )
    responsable_nom = serializers.CharField(
        source="responsable.user.get_full_name", read_only=True
    )
    statut_display = serializers.CharField(source="get_statut_display", read_only=True)
    membres_list = serializers.SerializerMethodField()

    class Meta:
        model = ProjetRecherche
        fields = [
            "id",
            "titre",
            "acronyme",
            "description",
            "laboratoire",
            "laboratoire_nom",
            "responsable",
            "responsable_nom",
            "membres",
            "membres_list",
            "financeur",
            "reference",
            "budget",
            "date_debut",
            "date_fin",
            "statut",
            "statut_display",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_membres_list(self, obj):
        return [{"id": m.id, "nom": m.user.get_full_name()} for m in obj.membres.all()]


class ProductionScientifiqueSerializer(serializers.ModelSerializer):
    """Serializer pour les productions scientifiques."""

    type_display = serializers.CharField(source="get_type_display", read_only=True)
    laboratoire_nom = serializers.CharField(
        source="laboratoire.acronyme", read_only=True
    )
    projet_titre = serializers.CharField(source="projet.titre", read_only=True)
    auteurs_list = serializers.SerializerMethodField()

    class Meta:
        model = ProductionScientifique
        fields = [
            "id",
            "type",
            "type_display",
            "titre",
            "auteurs",
            "auteurs_list",
            "laboratoire",
            "laboratoire_nom",
            "projet",
            "projet_titre",
            "annee",
            "doi",
            "url_hal",
            "facteur_impact",
            "fichier",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_auteurs_list(self, obj):
        return [{"id": a.id, "nom": a.user.get_full_name()} for a in obj.auteurs.all()]


class TheseListSerializer(serializers.ModelSerializer):
    """Serializer léger pour les thèses."""

    laboratoire_nom = serializers.CharField(
        source="laboratoire.acronyme", read_only=True
    )
    doctorant_nom = serializers.CharField(
        source="doctorant.user.get_full_name", read_only=True
    )
    directeur_nom = serializers.CharField(
        source="directeur.user.get_full_name", read_only=True
    )
    statut_display = serializers.CharField(source="get_statut_display", read_only=True)

    class Meta:
        model = These
        fields = [
            "id",
            "titre",
            "laboratoire",
            "laboratoire_nom",
            "doctorant_nom",
            "directeur_nom",
            "date_debut",
            "date_soutenance",
            "statut",
            "statut_display",
            "financement",
        ]


class TheseDetailSerializer(serializers.ModelSerializer):
    """Serializer complet pour une thèse."""

    laboratoire_nom = serializers.CharField(
        source="laboratoire.acronyme", read_only=True
    )
    doctorant_nom = serializers.CharField(
        source="doctorant.user.get_full_name", read_only=True
    )
    directeur_nom = serializers.CharField(
        source="directeur.user.get_full_name", read_only=True
    )
    co_directeur_nom = serializers.CharField(
        source="co_directeur.user.get_full_name", read_only=True
    )
    statut_display = serializers.CharField(source="get_statut_display", read_only=True)

    class Meta:
        model = These
        fields = [
            "id",
            "titre",
            "resume",
            "mots_cles",
            "laboratoire",
            "laboratoire_nom",
            "doctorant",
            "doctorant_nom",
            "directeur",
            "directeur_nom",
            "co_directeur",
            "co_directeur_nom",
            "date_debut",
            "date_soutenance",
            "statut",
            "statut_display",
            "financement",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]
