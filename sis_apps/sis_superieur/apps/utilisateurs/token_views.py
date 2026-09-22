"""Émission de jetons JWT avec application du MFA (TOTP) à la connexion.

Si l'utilisateur a activé le MFA (``mfa_active``), la connexion par
identifiant/mot de passe seule ne suffit plus : un ``mfa_code`` valide doit
être fourni dans la même requête. Ce comportement s'ajoute à
l'authentification fédérée Open edX (``EdxJWTAuthentication``), qui reste
le mécanisme principal en production ; ce point d'entrée sert aux comptes
locaux et aux clients qui s'authentifient directement contre le SIS.
"""

from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView

from sis_common.mfa import verify_code


class MFATokenObtainPairSerializer(TokenObtainPairSerializer):
    mfa_code = serializers.CharField(required=False, allow_blank=True, write_only=True)

    def validate(self, attrs):
        mfa_code = attrs.pop("mfa_code", "")
        data = super().validate(attrs)
        if getattr(self.user, "mfa_active", False) and not verify_code(self.user.mfa_secret, mfa_code):
            raise serializers.ValidationError(
                {"mfa_code": "Un code d'authentification à deux facteurs valide est requis."}
            )
        return data


class MFATokenObtainPairView(TokenObtainPairView):
    serializer_class = MFATokenObtainPairSerializer
