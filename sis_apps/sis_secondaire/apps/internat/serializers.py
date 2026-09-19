"""Serializers for internat (SIS Secondaire)."""

from django.db.models import Q
from rest_framework import serializers

from .models import BatimentInternat, Chambre, EtudeSurveillee, OccupantChambre


class BatimentInternatSerializer(serializers.ModelSerializer):
    """Serializer pour les bâtiments."""

    nb_chambres = serializers.SerializerMethodField()
    nb_places = serializers.SerializerMethodField()

    class Meta:
        model = BatimentInternat
        fields = [
            "id",
            "nom",
            "adresse",
            "nb_etages",
            "nb_chambres",
            "nb_places",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_nb_chambres(self, obj):
        return obj.chambres.count()

    def get_nb_places(self, obj):
        return sum(c.capacite for c in obj.chambres.all())


class ChambreListSerializer(serializers.ModelSerializer):
    """Serializer léger pour les chambres."""

    batiment_nom = serializers.CharField(source="batiment.nom", read_only=True)
    type_display = serializers.CharField(source="get_type_display", read_only=True)
    nb_occupants = serializers.SerializerMethodField()
    places_disponibles = serializers.SerializerMethodField()

    class Meta:
        model = Chambre
        fields = [
            "id",
            "batiment",
            "batiment_nom",
            "numero",
            "etage",
            "type",
            "type_display",
            "capacite",
            "nb_occupants",
            "places_disponibles",
        ]

    def get_nb_occupants(self, obj):
        from django.utils import timezone

        today = timezone.now().date()
        return (
            obj.occupants.filter(
                date_debut__lte=today,
            )
            .filter(Q(date_fin__isnull=True) | Q(date_fin__gte=today))
            .count()
        )

    def get_places_disponibles(self, obj):
        return obj.capacite - self.get_nb_occupants(obj)


class ChambreDetailSerializer(serializers.ModelSerializer):
    """Serializer complet pour une chambre."""

    batiment_nom = serializers.CharField(source="batiment.nom", read_only=True)
    type_display = serializers.CharField(source="get_type_display", read_only=True)

    class Meta:
        model = Chambre
        fields = [
            "id",
            "batiment",
            "batiment_nom",
            "numero",
            "etage",
            "type",
            "type_display",
            "capacite",
            "equipements",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class OccupantChambreSerializer(serializers.ModelSerializer):
    """Serializer pour les occupants."""

    eleve_matricule = serializers.CharField(source="eleve.matricule", read_only=True)
    eleve_nom = serializers.CharField(source="eleve.user.get_full_name", read_only=True)
    eleve_classe = serializers.CharField(source="eleve.classe.nom", read_only=True)
    chambre_numero = serializers.CharField(source="chambre.numero", read_only=True)
    batiment_nom = serializers.CharField(source="chambre.batiment.nom", read_only=True)

    class Meta:
        model = OccupantChambre
        fields = [
            "id",
            "chambre",
            "chambre_numero",
            "batiment_nom",
            "eleve",
            "eleve_matricule",
            "eleve_nom",
            "eleve_classe",
            "date_debut",
            "date_fin",
            "motif_fin",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class EtudeSurveilleeSerializer(serializers.ModelSerializer):
    """Serializer pour les études surveillées."""

    batiment_nom = serializers.CharField(source="batiment.nom", read_only=True)
    surveillant_nom = serializers.CharField(
        source="surveillant.get_full_name", read_only=True
    )
    nb_presents = serializers.SerializerMethodField()

    class Meta:
        model = EtudeSurveillee
        fields = [
            "id",
            "batiment",
            "batiment_nom",
            "salle",
            "date",
            "heure_debut",
            "heure_fin",
            "surveillant",
            "surveillant_nom",
            "eleves_presents",
            "nb_presents",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_nb_presents(self, obj):
        return obj.eleves_presents.count()
