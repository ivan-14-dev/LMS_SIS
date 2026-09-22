"""Récupération de compte par email (API non authentifiée).

Ces vues sont volontairement en dehors du ``UtilisateursViewSet`` (qui
exige une authentification) : elles doivent rester accessibles à un
utilisateur qui a perdu l'accès à son compte. Le throttling anonyme DRF
(voir ``REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']``) limite les abus.
"""

from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from sis_common.account_recovery import confirm_password_reset, request_password_reset

from .models import Utilisateur
from .serializers import PasswordResetConfirmSerializer, PasswordResetRequestSerializer

_GENERIC_DETAIL = (
    "Si un compte actif correspond à cet email, un lien de réinitialisation vient de lui être envoyé."
)


class PasswordResetRequestView(APIView):
    """Déclenche l'envoi d'un email de réinitialisation de mot de passe."""

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        request_password_reset(Utilisateur, serializer.validated_data["email"])
        # Réponse générique dans tous les cas, pour éviter l'énumération de comptes.
        return Response({"detail": _GENERIC_DETAIL})


class PasswordResetConfirmView(APIView):
    """Valide le jeton reçu par email et applique le nouveau mot de passe."""

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        success = confirm_password_reset(
            Utilisateur,
            serializer.validated_data["uid"],
            serializer.validated_data["token"],
            serializer.validated_data["new_password"],
        )
        if not success:
            return Response({"detail": "Lien de réinitialisation invalide ou expiré."}, status=400)
        return Response({"detail": "Mot de passe réinitialisé avec succès."})
