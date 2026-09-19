"""Serializers for enseignants (SIS Supérieur)."""

from rest_framework import serializers

from .models import AffectationEnseignement, EnseignantChercheur


class EnseignantListSerializer(serializers.ModelSerializer):
    """Serializer léger pour les listes d'enseignants."""

    full_name = serializers.CharField(source="user.get_full_name", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    corps_display = serializers.CharField(source="get_corps_display", read_only=True)
    laboratoire_nom = serializers.CharField(source="laboratoire.nom", read_only=True)

    class Meta:
        model = EnseignantChercheur
        fields = [
            "id",
            "full_name",
            "email",
            "numero_harpe",
            "corps",
            "corps_display",
            "specialite",
            "laboratoire",
            "laboratoire_nom",
            "h_index",
        ]


class EnseignantDetailSerializer(serializers.ModelSerializer):
    """Serializer complet pour le détail d'un enseignant."""

    full_name = serializers.CharField(source="user.get_full_name", read_only=True)
    first_name = serializers.CharField(source="user.first_name", read_only=True)
    last_name = serializers.CharField(source="user.last_name", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    corps_display = serializers.CharField(source="get_corps_display", read_only=True)
    laboratoire_nom = serializers.CharField(source="laboratoire.nom", read_only=True)

    class Meta:
        model = EnseignantChercheur
        fields = [
            "id",
            "user",
            "full_name",
            "first_name",
            "last_name",
            "email",
            "numero_harpe",
            "corps",
            "corps_display",
            "specialite",
            "laboratoire",
            "laboratoire_nom",
            "h_index",
            "orcid",
            "id_hal",
            "id_ref",
            "bibliographie",
            "annee_these",
            "directeur_these",
            "heures_service",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
        extra_kwargs = {
            "rib_iban": {"write_only": True},
        }


class AffectationEnseignementSerializer(serializers.ModelSerializer):
    """Serializer pour les affectations d'enseignement."""

    enseignant_nom = serializers.CharField(
        source="enseignant.user.get_full_name", read_only=True
    )
    ue_nom = serializers.CharField(source="ue.nom", read_only=True)
    ecue_nom = serializers.CharField(source="ecue.nom", read_only=True)
    annee_libelle = serializers.CharField(
        source="annee_universitaire.libelle", read_only=True
    )
    type_display = serializers.SerializerMethodField()

    class Meta:
        model = AffectationEnseignement
        fields = [
            "id",
            "enseignant",
            "enseignant_nom",
            "ue",
            "ue_nom",
            "ecue",
            "ecue_nom",
            "type_enseignement",
            "type_display",
            "heures",
            "annee_universitaire",
            "annee_libelle",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_type_display(self, obj):
        return dict(obj._meta.get_field("type_enseignement").choices).get(
            obj.type_enseignement, ""
        )


class EnseignantCreateSerializer(serializers.ModelSerializer):
    """Serializer pour la création d'un enseignant."""

    username = serializers.CharField(write_only=True)
    email = serializers.EmailField(write_only=True)
    first_name = serializers.CharField(write_only=True)
    last_name = serializers.CharField(write_only=True)
    password = serializers.CharField(write_only=True)

    class Meta:
        model = EnseignantChercheur
        fields = [
            "username",
            "email",
            "first_name",
            "last_name",
            "password",
            "numero_harpe",
            "corps",
            "specialite",
            "laboratoire",
            "orcid",
            "id_hal",
            "heures_service",
        ]

    def create(self, validated_data):
        from apps.utilisateurs.models import Utilisateur

        user_data = {
            "username": validated_data.pop("username"),
            "email": validated_data.pop("email"),
            "first_name": validated_data.pop("first_name"),
            "last_name": validated_data.pop("last_name"),
            "role": "enseignant",
        }
        password = validated_data.pop("password")

        user = Utilisateur(**user_data)
        user.set_password(password)
        user.save()

        enseignant = EnseignantChercheur.objects.create(user=user, **validated_data)
        return enseignant
