"""Serializers for infirmerie (SIS Secondaire)."""

from rest_framework import serializers

from .models import DossierMedical, StockMedicament, VisiteInfirmerie


class DossierMedicalSerializer(serializers.ModelSerializer):
    """Serializer pour les dossiers médicaux (accès restreint)."""

    eleve_matricule = serializers.CharField(source="eleve.matricule", read_only=True)
    eleve_nom = serializers.CharField(source="eleve.user.get_full_name", read_only=True)
    eleve_classe = serializers.CharField(source="eleve.classe.nom", read_only=True)

    class Meta:
        model = DossierMedical
        fields = [
            "id",
            "eleve",
            "eleve_matricule",
            "eleve_nom",
            "eleve_classe",
            "groupe_sanguin",
            "allergies",
            "maladies_chroniques",
            "traitements",
            "vaccinations",
            "medecin_traitant",
            "telephone_medecin",
            "observations",
            "date_derniere_visite",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class VisiteInfirmerieListSerializer(serializers.ModelSerializer):
    """Serializer léger pour les visites."""

    eleve_matricule = serializers.CharField(source="eleve.matricule", read_only=True)
    eleve_nom = serializers.CharField(source="eleve.user.get_full_name", read_only=True)
    eleve_classe = serializers.CharField(source="eleve.classe.nom", read_only=True)
    orientation_display = serializers.CharField(
        source="get_orientation_display", read_only=True
    )
    infirmier_nom = serializers.CharField(
        source="infirmier.get_full_name", read_only=True
    )

    class Meta:
        model = VisiteInfirmerie
        fields = [
            "id",
            "eleve",
            "eleve_matricule",
            "eleve_nom",
            "eleve_classe",
            "date",
            "heure_arrivee",
            "heure_sortie",
            "motif",
            "orientation",
            "orientation_display",
            "infirmier",
            "infirmier_nom",
            "parents_prevenus",
        ]


class VisiteInfirmerieDetailSerializer(serializers.ModelSerializer):
    """Serializer complet pour une visite."""

    eleve_matricule = serializers.CharField(source="eleve.matricule", read_only=True)
    eleve_nom = serializers.CharField(source="eleve.user.get_full_name", read_only=True)
    eleve_classe = serializers.CharField(source="eleve.classe.nom", read_only=True)
    orientation_display = serializers.CharField(
        source="get_orientation_display", read_only=True
    )
    infirmier_nom = serializers.CharField(
        source="infirmier.get_full_name", read_only=True
    )

    class Meta:
        model = VisiteInfirmerie
        fields = [
            "id",
            "eleve",
            "eleve_matricule",
            "eleve_nom",
            "eleve_classe",
            "date",
            "heure_arrivee",
            "heure_sortie",
            "motif",
            "symptomes",
            "soins",
            "traitement_administre",
            "orientation",
            "orientation_display",
            "infirmier",
            "infirmier_nom",
            "parents_prevenus",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class StockMedicamentSerializer(serializers.ModelSerializer):
    """Serializer pour le stock de médicaments."""

    en_alerte = serializers.BooleanField(read_only=True)
    perime = serializers.SerializerMethodField()

    class Meta:
        model = StockMedicament
        fields = [
            "id",
            "nom",
            "description",
            "quantite",
            "seuil_alerte",
            "unite",
            "date_peremption",
            "numero_lot",
            "en_alerte",
            "perime",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_perime(self, obj):
        from django.utils import timezone

        if obj.date_peremption:
            return obj.date_peremption < timezone.now().date()
        return False
