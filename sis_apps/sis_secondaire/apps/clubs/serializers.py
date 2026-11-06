"""Serializers for clubs (SIS Secondaire)."""

from django.db import transaction
from rest_framework import serializers

from sis_common.serializers import TenantBoundSerializerMixin

from .models import Club, MembreClub, SeanceClub


class ClubListSerializer(serializers.ModelSerializer):
    """Serializer léger pour les listes de clubs."""

    type_display = serializers.CharField(source="get_type_display", read_only=True)
    responsable_nom = serializers.CharField(source="responsable.get_full_name", read_only=True)
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


class ClubDetailSerializer(TenantBoundSerializerMixin, serializers.ModelSerializer):
    """Serializer complet pour un club."""

    type_display = serializers.CharField(source="get_type_display", read_only=True)
    responsable_nom = serializers.CharField(source="responsable.get_full_name", read_only=True)
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

    @transaction.atomic
    def update(self, instance, validated_data):
        club = Club.objects.select_for_update().get(pk=instance.pk)
        if (
            "capacite" in validated_data
            and MembreClub.objects.filter(club=club, statut="actif").count() > validated_data["capacite"]
        ):
            raise serializers.ValidationError(
                {"capacite": "La capacité ne peut être inférieure au nombre de membres actifs."}
            )
        return super().update(club, validated_data)


class MembreClubSerializer(TenantBoundSerializerMixin, serializers.ModelSerializer):
    """Serializer pour les membres."""

    club_nom = serializers.CharField(source="club.nom", read_only=True)
    eleve_matricule = serializers.CharField(source="eleve.matricule", read_only=True)
    eleve_nom = serializers.CharField(source="eleve.user.get_full_name", read_only=True)
    eleve_classe = serializers.CharField(source="eleve.classe_actuelle.nom", read_only=True)
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

    def _check_capacity(self, attrs, instance=None):
        club = attrs.get("club", instance.club if instance is not None else None)
        statut = attrs.get("statut", instance.statut if instance is not None else "actif")
        if statut != "actif" or (
            instance is not None and instance.statut == "actif" and instance.club_id == club.pk
        ):
            return

        club = Club.objects.select_for_update().get(pk=club.pk)
        membres = MembreClub.objects.filter(club=club, statut="actif")
        if instance is not None:
            membres = membres.exclude(pk=instance.pk)
        if membres.count() >= club.capacite:
            raise serializers.ValidationError({"club": "La capacité du club est atteinte."})

    @transaction.atomic
    def create(self, validated_data):
        self._check_capacity(validated_data)
        return super().create(validated_data)

    @transaction.atomic
    def update(self, instance, validated_data):
        self._check_capacity(validated_data, instance)
        return super().update(instance, validated_data)


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
