"""Serializers for entreprises (SIS Supérieur)."""

from rest_framework import serializers

from .models import ContactEntreprise, Entreprise


class EntrepriseListSerializer(serializers.ModelSerializer):
    """Serializer léger pour les listes d'entreprises."""

    type_display = serializers.CharField(source="get_type_display", read_only=True)
    secteur_display = serializers.CharField(
        source="get_secteur_display", read_only=True
    )
    nb_contacts = serializers.SerializerMethodField()
    nb_offres = serializers.SerializerMethodField()

    class Meta:
        model = Entreprise
        fields = [
            "id",
            "raison_sociale",
            "type",
            "type_display",
            "secteur",
            "secteur_display",
            "ville",
            "pays",
            "taille",
            "nb_contacts",
            "nb_offres",
            "actif",
        ]

    def get_nb_contacts(self, obj):
        return obj.contacts.filter(actif=True).count()

    def get_nb_offres(self, obj):
        return obj.offres_stage.count()


class EntrepriseDetailSerializer(serializers.ModelSerializer):
    """Serializer complet pour une entreprise."""

    type_display = serializers.CharField(source="get_type_display", read_only=True)
    secteur_display = serializers.CharField(
        source="get_secteur_display", read_only=True
    )
    nb_contacts = serializers.SerializerMethodField()
    nb_offres = serializers.SerializerMethodField()

    class Meta:
        model = Entreprise
        fields = [
            "id",
            "raison_sociale",
            "type",
            "type_display",
            "siret",
            "siren",
            "tva_intracommunautaire",
            "secteur",
            "secteur_display",
            "description",
            "site_web",
            "adresse",
            "code_postal",
            "ville",
            "pays",
            "telephone",
            "email",
            "logo",
            "taille",
            "nb_contacts",
            "nb_offres",
            "actif",
            "cree_le",
            "modifie_le",
        ]
        read_only_fields = ["id", "cree_le", "modifie_le"]

    def get_nb_contacts(self, obj):
        return obj.contacts.filter(actif=True).count()

    def get_nb_offres(self, obj):
        return obj.offres_stage.count()


class ContactEntrepriseSerializer(serializers.ModelSerializer):
    """Serializer pour les contacts."""

    entreprise_nom = serializers.CharField(
        source="entreprise.raison_sociale", read_only=True
    )
    role_display = serializers.CharField(source="get_role_display", read_only=True)
    nom_complet = serializers.SerializerMethodField()

    class Meta:
        model = ContactEntreprise
        fields = [
            "id",
            "entreprise",
            "entreprise_nom",
            "nom",
            "prenom",
            "nom_complet",
            "role",
            "role_display",
            "fonction",
            "email",
            "telephone",
            "actif",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_nom_complet(self, obj):
        return f"{obj.prenom} {obj.nom}"
