"""Serializers for clubs (SIS Secondaire)."""

from rest_framework import serializers

from .models import Club, MembreClub, SeanceClub


class ClubListSerializer(serializers.ModelSerializer):
    """Serializer léger pour les listes de clubs."""

    type_display = serializers.CharField(source="get_type_display", read_only=True)
    responsable_nom = serializers.CharField(
        source="responsable.get_full_name", read_only=True
    )
    nb_membres = serializers.SerializerMethodField()

    class Meta:
        model = Club
        fields = [
            "id",
            "nom",
            "type",
            "type_display",
            "responsable_nom",
            "horaires",
            "capacite",
            "nb_membres",
            "actif",
            "couleur",
        ]

    def get_nb_membres(self, obj):
        return obj.membres.filter(statut="actif").count()


class ClubDetailSerializer(serializers.ModelSerializer):
    """Serializer complet pour un club."""

    type_display = serializers.CharField(source="get_type_display", read_only=True)
    responsable_nom = serializers.CharField(
        source="responsable.get_full_name", read_only=True
    )
    nb_membres = serializers.SerializerMethodField()

    class Meta:
        model = Club
        fields = [
            "id",
            "nom",
            "type",
            "type_display",
            "description",
            "responsable",
            "responsable_nom",
            "salle",
            "horaires",
            "capacite",
            "image",
            "couleur",
            "date_creation",
            "nb_membres",
            "actif",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_nb_membres(self, obj):
        return obj.membres.filter(statut="actif").count()


class MembreClubSerializer(serializers.ModelSerializer):
    """Serializer pour les membres."""

    club_nom = serializers.CharField(source="club.nom", read_only=True)
    eleve_matricule = serializers.CharField(source="eleve.matricule", read_only=True)
    eleve_nom = serializers.CharField(source="eleve.user.get_full_name", read_only=True)
    eleve_classe = serializers.CharField(source="eleve.classe.nom", read_only=True)
    statut_display = serializers.CharField(source="get_statut_display", read_only=True)

    class Meta:
        model = MembreClub
        fields = [
            "id",
            "club",
            "club_nom",
            "eleve",
            "eleve_matricule",
            "eleve_nom",
            "eleve_classe",
            "date_inscription",
            "statut",
            "statut_display",
        ]
        read_only_fields = ["id", "date_inscription"]


class SeanceClubSerializer(serializers.ModelSerializer):
    """Serializer pour les séances."""

    club_nom = serializers.CharField(source="club.nom", read_only=True)
    nb_presents = serializers.SerializerMethodField()

    class Meta:
        model = SeanceClub
        fields = [
            "id",
            "club",
            "club_nom",
            "date",
            "heure_debut",
            "heure_fin",
            "activite",
            "presents",
            "nb_presents",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_nb_presents(self, obj):
        return obj.presents.count()
