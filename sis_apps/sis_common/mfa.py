"""Authentification à deux facteurs (TOTP) partagée entre les SIS.

L'enrôlement se déroule en deux temps, comme recommandé par la RFC 6238 et
les bonnes pratiques OWASP :

1. ``begin_enrollment`` génère un secret TOTP et le stocke (chiffré via
   ``EncryptedCharField``) sur l'utilisateur, mais n'active PAS encore le
   MFA. Le client affiche le QR code / secret et demande à l'utilisateur de
   saisir un code généré par son application d'authentification.
2. ``confirm_enrollment`` vérifie ce premier code et n'active ``mfa_active``
   qu'à ce moment-là, garantissant que l'utilisateur a bien configuré son
   application avant que le MFA ne devienne obligatoire à la connexion.

Une fois actif, ``verify_code`` est utilisé à la fois pour la vérification
de connexion (voir ``apps.utilisateurs.token_views``) et pour la
désactivation du MFA (qui exige un code valide, en plus du mot de passe).
"""

import pyotp


def generate_secret() -> str:
    """Génère un nouveau secret TOTP aléatoire (base32)."""
    return pyotp.random_base32()


def get_provisioning_uri(user, secret: str, issuer: str = "SIS") -> str:
    """Construit l'URI ``otpauth://`` utilisée pour générer le QR code."""
    label = user.email or user.get_username()
    return pyotp.totp.TOTP(secret).provisioning_uri(name=label, issuer_name=issuer)


def verify_code(secret: str, code: str) -> bool:
    """Vérifie un code TOTP à 6 chiffres, avec une tolérance d'une période."""
    if not secret or not code:
        return False
    try:
        return pyotp.TOTP(secret).verify(code.strip(), valid_window=1)
    except Exception:
        return False


def begin_enrollment(user) -> tuple[str, str]:
    """Démarre l'enrôlement MFA : génère et stocke un secret non activé.

    Returns:
        Un tuple ``(secret, provisioning_uri)``.
    """
    secret = generate_secret()
    user.mfa_secret = secret
    user.mfa_active = False
    user.save(update_fields=["mfa_secret", "mfa_active"])
    return secret, get_provisioning_uri(user, secret)


def confirm_enrollment(user, code: str) -> bool:
    """Valide le premier code TOTP et active le MFA si correct."""
    if not verify_code(user.mfa_secret, code):
        return False
    user.mfa_active = True
    user.save(update_fields=["mfa_active"])
    return True


def disable_mfa(user) -> None:
    """Désactive le MFA et efface le secret stocké."""
    user.mfa_active = False
    user.mfa_secret = ""
    user.save(update_fields=["mfa_active", "mfa_secret"])
