"""Serializers for utilisateurs (SIS Secondaire)."""

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
    """Serializer léger pour les listes d'utilisateurs."""

    full_name = serializers.CharField(source="get_full_name", read_only=True)
    role_display = serializers.CharField(source="get_role_display", read_only=True)

    class Meta:
        model = Utilisateur
        fields = [
            "id",
            "username",
            "email",
            "full_name",
            "role",
            "role_display",
            "groups",
            "is_active",
        ]


class UtilisateurDetailSerializer(serializers.ModelSerializer):
    """Serializer complet pour le détail d'un utilisateur."""

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
            "is_active",
            "is_staff",
            "etablissement",
            "groups",
            "user_permissions",
            "attributs_acces",
            "telephone",
            "avatar",
            "date_joined",
            "last_login",
        ]
        read_only_fields = ["id", "date_joined", "last_login"]


class UtilisateurCreateSerializer(serializers.ModelSerializer):
    """Serializer pour la création d'utilisateur."""

    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = Utilisateur
        fields = [
            "username",
            "email",
            "first_name",
            "last_name",
            "password",
            "password_confirm",
            "role",
            "etablissement",
        ]

    def validate(self, attrs):
        if attrs["password"] != attrs.pop("password_confirm"):
            raise serializers.ValidationError({"password_confirm": "Les mots de passe ne correspondent pas."})
        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = Utilisateur(**validated_data)
        user.set_password(password)
        user.save()
        return user


class ChangePasswordSerializer(serializers.Serializer):
    """Serializer pour le changement de mot de passe."""

    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, validators=[validate_password])

    def validate_old_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("L'ancien mot de passe est incorrect.")
        return value


class UtilisateurProfileSerializer(serializers.ModelSerializer):
    """Serializer pour la mise à jour du profil (utilisateur connecté)."""

    class Meta:
        model = Utilisateur
        fields = ["first_name", "last_name", "telephone", "photo"]


class RevokeSessionSerializer(serializers.Serializer):
    """Serializer pour la révocation granulaire d'une session JWT précise."""

    jti = serializers.CharField(required=True, max_length=255)


class MFACodeSerializer(serializers.Serializer):
    """Serializer pour la confirmation d'enrôlement / vérification MFA."""

    code = serializers.CharField(required=True, max_length=10)


class MFADisableSerializer(serializers.Serializer):
    """Serializer pour la désactivation du MFA (double confirmation)."""

    password = serializers.CharField(required=True)
    code = serializers.CharField(required=True, max_length=10)


class PasswordResetRequestSerializer(serializers.Serializer):
    """Serializer pour la demande de réinitialisation de mot de passe."""

    email = serializers.EmailField(required=True)


class PasswordResetConfirmSerializer(serializers.Serializer):
    """Serializer pour la confirmation de réinitialisation de mot de passe."""

    uid = serializers.CharField(required=True)
    token = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, validators=[validate_password])
