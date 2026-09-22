"""Révocation de session partagée pour les SIS secondaire et supérieur.

Les SIS authentifient les requêtes via trois mécanismes possibles
(fédération d'identité Open edX, `TokenAuthentication` DRF et SimpleJWT).
Pour "déconnecter" complètement un utilisateur — par exemple après un
changement de mot de passe ou une action administrative de sécurité — il
faut donc :

- supprimer son jeton `rest_framework.authtoken.models.Token` (un seul
  jeton statique par utilisateur, sa suppression invalide immédiatement
  toute requête `TokenAuthentication`) ;
- mettre en liste noire tous les jetons de rafraîchissement SimpleJWT
  encore actifs (`OutstandingToken`), via l'application
  `rest_framework_simplejwt.token_blacklist`, empêchant l'émission de
  nouveaux jetons d'accès à partir de ces refresh tokens.

Cette fonction est volontairement tolérante : si l'application de
blacklist n'est pas installée ou si l'utilisateur n'a pas de token, elle
ne lève pas d'erreur.
"""

import logging

logger = logging.getLogger(__name__)


def revoke_all_sessions(user) -> dict:
    """Révoque tous les moyens d'authentification actifs d'un utilisateur.

    Args:
        user: instance du modèle utilisateur SIS à déconnecter partout.

    Returns:
        Un résumé des actions effectuées, utile pour les réponses API et
        les tests : ``{"token_revoked": bool, "jwt_tokens_revoked": int}``.
    """
    summary = {"token_revoked": False, "jwt_tokens_revoked": 0}

    try:
        from rest_framework.authtoken.models import Token

        deleted, _ = Token.objects.filter(user=user).delete()
        summary["token_revoked"] = bool(deleted)
    except Exception:  # pragma: no cover - authtoken toujours installé en pratique
        logger.exception("Impossible de révoquer le token DRF de l'utilisateur %s", user.pk)

    try:
        from rest_framework_simplejwt.token_blacklist.models import (
            BlacklistedToken,
            OutstandingToken,
        )

        outstanding = OutstandingToken.objects.filter(user=user)
        revoked = 0
        for token in outstanding:
            _, created = BlacklistedToken.objects.get_or_create(token=token)
            if created:
                revoked += 1
        summary["jwt_tokens_revoked"] = revoked
    except Exception:  # pragma: no cover - app de blacklist non installée
        logger.debug(
            "Blacklist SimpleJWT indisponible : aucun jeton JWT révoqué pour l'utilisateur %s",
            user.pk,
        )

    return summary
