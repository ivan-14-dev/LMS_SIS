"""Récupération de compte par email, partagée entre les SIS.

Le flux suit le standard Django (``PasswordResetTokenGenerator`` +
``uidb64``) déjà utilisé par ``django.contrib.auth`` pour l'admin, adapté
ici à une API DRF stateless :

1. ``request_password_reset`` cherche l'utilisateur par email dans le
   schéma du tenant courant, et lui envoie (s'il existe et est actif) un
   email contenant un lien ``{FRONTEND_URL}/reset-password/{uid}/{token}/``.
   Par conception, la fonction ne révèle jamais si l'email existe ou non :
   l'appelant doit toujours renvoyer la même réponse générique.
2. ``confirm_password_reset`` valide le couple ``(uid, token)`` et, si
   valide, définit le nouveau mot de passe puis révoque toutes les sessions
   actives de l'utilisateur (voir ``sis_common.session_security``), afin
   qu'un éventuel attaquant ayant compromis l'ancien mot de passe perde
   immédiatement l'accès.

Le générateur de jeton intègre le mot de passe courant et ``last_login``
dans son hash : un jeton devient donc automatiquement invalide dès qu'il a
été utilisé une fois ou que le mot de passe a changé entretemps.
"""

import logging

from django.conf import settings
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from sis_common.session_security import revoke_all_sessions

logger = logging.getLogger(__name__)

_token_generator = PasswordResetTokenGenerator()


def request_password_reset(user_model, email: str) -> None:
    """Envoie un email de réinitialisation si un compte actif correspond.

    N'échoue jamais et ne renvoie aucune information permettant de deviner
    si l'email correspond à un compte existant (protection contre
    l'énumération de comptes).
    """
    if not email:
        return

    user = user_model.objects.filter(email__iexact=email, is_active=True).first()
    if user is None:
        logger.info("Demande de réinitialisation pour un email inconnu ou inactif.")
        return

    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = _token_generator.make_token(user)
    frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:3000").rstrip("/")
    reset_link = f"{frontend_url}/reset-password/{uid}/{token}/"

    send_mail(
        subject="Réinitialisation de votre mot de passe SIS",
        message=(
            "Vous avez demandé la réinitialisation de votre mot de passe.\n\n"
            f"Cliquez sur ce lien pour choisir un nouveau mot de passe : {reset_link}\n\n"
            "Si vous n'êtes pas à l'origine de cette demande, ignorez cet email : "
            "votre mot de passe actuel reste inchangé."
        ),
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@sis.local"),
        recipient_list=[user.email],
        fail_silently=True,
    )


def confirm_password_reset(user_model, uidb64: str, token: str, new_password: str) -> bool:
    """Valide le jeton et applique le nouveau mot de passe.

    Returns:
        ``True`` si la réinitialisation a réussi, ``False`` si le jeton ou
        l'identifiant est invalide/expiré.
    """
    try:
        uid = force_bytes(urlsafe_base64_decode(uidb64)).decode()
        user = user_model.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, user_model.DoesNotExist):
        return False

    if not _token_generator.check_token(user, token):
        return False

    user.set_password(new_password)
    user.save(update_fields=["password"])
    revoke_all_sessions(user)
    return True
