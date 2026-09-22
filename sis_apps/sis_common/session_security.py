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


def list_active_sessions(user) -> list:
    """Liste les sessions JWT (jetons de rafraîchissement) d'un utilisateur.

    Chaque connexion via ``auth/token/`` émet un nouveau jeton de
    rafraîchissement SimpleJWT distinct (``OutstandingToken``) : une entrée
    de cette liste correspond donc, en pratique, à un appareil ou navigateur
    connecté. Ce module ne capture pas de métadonnées d'appareil (user-agent,
    adresse IP) : seules l'identité du jeton (``jti``) et ses horodatages
    sont disponibles.

    Args:
        user: instance du modèle utilisateur SIS.

    Returns:
        Liste de dictionnaires triés du plus récent au plus ancien :
        ``{"jti": str, "created_at": datetime, "expires_at": datetime,
        "revoked": bool}``. Liste vide si l'application de blacklist
        SimpleJWT n'est pas installée.
    """
    try:
        from rest_framework_simplejwt.token_blacklist.models import (
            BlacklistedToken,
            OutstandingToken,
        )
    except Exception:  # pragma: no cover - app de blacklist non installée
        logger.debug("Blacklist SimpleJWT indisponible : aucune session listée pour %s", user.pk)
        return []

    blacklisted_ids = set(
        BlacklistedToken.objects.filter(token__user=user).values_list("token_id", flat=True)
    )
    sessions = []
    for token in OutstandingToken.objects.filter(user=user).order_by("-created_at"):
        sessions.append(
            {
                "jti": token.jti,
                "created_at": token.created_at,
                "expires_at": token.expires_at,
                "revoked": token.id in blacklisted_ids,
            }
        )
    return sessions


def revoke_session(user, jti: str) -> "dict | None":
    """Révoque une seule session (jeton de rafraîchissement) d'un utilisateur.

    Contrairement à :func:`revoke_all_sessions`, cette fonction ne déconnecte
    qu'un appareil/navigateur précis, identifié par le ``jti`` de son jeton
    de rafraîchissement (obtenu via :func:`list_active_sessions`), sans
    invalider les autres sessions actives ni le jeton DRF statique.

    Args:
        user: instance du modèle utilisateur SIS propriétaire de la session.
        jti: identifiant unique du jeton de rafraîchissement à révoquer.

    Returns:
        ``None`` si le jeton n'existe pas (ou n'appartient pas à ``user``,
        ou si l'application de blacklist n'est pas installée). Sinon un
        résumé ``{"jti": str, "already_revoked": bool}``.
    """
    try:
        from rest_framework_simplejwt.token_blacklist.models import (
            BlacklistedToken,
            OutstandingToken,
        )
    except Exception:  # pragma: no cover - app de blacklist non installée
        logger.debug("Blacklist SimpleJWT indisponible : révocation ignorée pour %s", user.pk)
        return None

    try:
        token = OutstandingToken.objects.get(user=user, jti=jti)
    except OutstandingToken.DoesNotExist:
        return None

    _, created = BlacklistedToken.objects.get_or_create(token=token)
    return {"jti": jti, "already_revoked": not created}
