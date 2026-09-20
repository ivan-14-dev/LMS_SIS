"""Serializers for utilisateurs (SIS Supérieur)."""

from django.contrib.auth.models import Group, Permission
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import Utilisateur


class PermissionSerializer(serializers.ModelSerializer):
    app_label = serializers.CharField(source="content_type.app_label", read_only=True)

    class Meta:
        model = Permission
        fields = ["id", "app_label", "codename", "name"]


class GroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = ["id", "name", "permissions"]


class UtilisateurListSerializer(serializers.ModelSerializer):
    """Serializer léger pour les listes."""

    full_name = serializers.CharField(source="get_full_name", read_only=True)
    role_display = serializers.CharField(source="get_role_display", read_only=True)

    class Meta:
        model = Utilisateur
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "role",
            "role_display",
            "groups",
            "is_active",
        ]
        read_only_fields = ["id", "full_name", "role_display"]


class UtilisateurDetailSerializer(serializers.ModelSerializer):
    """Serializer complet pour le détail."""

    full_name = serializers.CharField(source="get_full_name", read_only=True)
    role_display = serializers.CharField(source="get_role_display", read_only=True)
    is_etudiant = serializers.BooleanField(read_only=True)
    is_enseignant = serializers.BooleanField(read_only=True)
    is_admin = serializers.BooleanField(read_only=True)

    class Meta:
        model = Utilisateur
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "role",
            "role_display",
            "etablissement",
            "groups",
            "user_permissions",
            "attributs_acces",
            "numero_etudiant",
            "numero_enseignant",
            "telephone",
            "adresse",
            "photo",
            "langue",
            "mfa_active",
            "doit_changer_mdp",
            "derniere_connexion",
            "preferences_notification",
            "is_active",
            "date_joined",
            "is_etudiant",
            "is_enseignant",
            "is_admin",
        ]
        read_only_fields = [
            "id",
            "full_name",
            "role_display",
            "derniere_connexion",
            "date_joined",
            "is_etudiant",
            "is_enseignant",
            "is_admin",
        ]
        extra_kwargs = {
            "mfa_secret": {"write_only": True},
        }


class UtilisateurCreateSerializer(serializers.ModelSerializer):
    """Serializer pour la création d'utilisateur."""

    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = Utilisateur
        fields = [
            "username",
            "email",
            "password",
            "password_confirm",
            "first_name",
            "last_name",
            "role",
            "etablissement",
            "telephone",
            "langue",
        ]

    def validate(self, attrs):
        if attrs.get("password") != attrs.get("password_confirm"):
            raise serializers.ValidationError(
                {"password_confirm": "Les mots de passe ne correspondent pas."}
            )
        return attrs

    def create(self, validated_data):
        validated_data.pop("password_confirm")
        password = validated_data.pop("password")
        user = Utilisateur(**validated_data)
        user.set_password(password)
        user.save()
        return user


class ChangePasswordSerializer(serializers.Serializer):
    """Serializer pour le changement de mot de passe."""

    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, validators=[validate_password])
    new_password_confirm = serializers.CharField(required=True)

    def validate(self, attrs):
        if attrs["new_password"] != attrs["new_password_confirm"]:
            raise serializers.ValidationError(
                {"new_password_confirm": "Les mots de passe ne correspondent pas."}
            )
        return attrs


class UtilisateurProfileSerializer(serializers.ModelSerializer):
    """Serializer pour mise à jour du profil (par l'utilisateur lui-même)."""

    class Meta:
        model = Utilisateur
        fields = [
            "first_name",
            "last_name",
            "telephone",
            "adresse",
            "photo",
            "langue",
            "preferences_notification",
        ]
from django.contrib.auth.models import Group, Permission
