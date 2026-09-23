"""Champs Django chiffrés au repos (Fernet) pour les données sensibles du SIS.

Ces champs sont destinés aux secrets MFA, aux coordonnées bancaires et aux
données médicales, qui doivent être stockés chiffrés plutôt qu'en clair.
Le chiffrement/déchiffrement est transparent pour le reste de l'application :
la valeur Python manipulée par le code métier reste en clair, seule la
représentation stockée en base est chiffrée.
"""

import json

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import models


def _get_fernet() -> Fernet:
    key = getattr(settings, "FIELD_ENCRYPTION_KEY", None)
    if not key:
        raise ImproperlyConfigured(
            "FIELD_ENCRYPTION_KEY doit être défini pour utiliser les champs chiffrés."
        )
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_value(raw: str) -> str:
    """Chiffre une chaîne et retourne un jeton texte stockable en base."""
    return _get_fernet().encrypt(raw.encode("utf-8")).decode("ascii")


def decrypt_value(token: str) -> str:
    """Déchiffre un jeton produit par :func:`encrypt_value`."""
    return _get_fernet().decrypt(token.encode("ascii")).decode("utf-8")


class EncryptedFieldMixin:
    """Stocke la valeur du champ chiffrée avec Fernet dans une colonne texte.

    Les données existantes non chiffrées (avant migration) sont conservées :
    si le déchiffrement échoue, la valeur brute lue en base est renvoyée telle
    quelle plutôt que de lever une erreur ou de perdre la donnée.
    """

    def db_type(self, connection):
        return "text"

    def get_internal_type(self):
        return "TextField"

    def _to_storage(self, value) -> str:
        """Sérialise la valeur Python en texte avant chiffrement."""
        return value if isinstance(value, str) else json.dumps(value)

    def _from_storage(self, raw: str):
        """Reconstruit la valeur Python à partir du texte déchiffré."""
        return raw

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        if value in (None, ""):
            return value
        return encrypt_value(self._to_storage(value))

    def from_db_value(self, value, expression, connection):
        if value in (None, ""):
            return value
        try:
            raw = decrypt_value(value)
        except (InvalidToken, ValueError, UnicodeDecodeError):
            # Donnée pré-existante non chiffrée (avant migration) : on la
            # renvoie telle quelle pour éviter toute perte de données. Elle
            # sera chiffrée à la prochaine sauvegarde.
            return value
        return self._from_storage(raw)


class EncryptedCharField(EncryptedFieldMixin, models.CharField):
    """CharField chiffré au repos. `max_length` continue de valider la valeur en clair."""


class EncryptedTextField(EncryptedFieldMixin, models.TextField):
    """TextField chiffré au repos."""


class EncryptedJSONField(EncryptedFieldMixin, models.JSONField):
    """JSONField chiffré au repos (sérialisation JSON avant chiffrement)."""

    def _to_storage(self, value) -> str:
        return json.dumps(value)

    def _from_storage(self, raw: str):
        return json.loads(raw)

    def from_db_value(self, value, expression, connection):
        if value in (None, ""):
            return self.get_default() if self.has_default() else value
        try:
            raw = decrypt_value(value)
        except (InvalidToken, ValueError, UnicodeDecodeError):
            # Donnée pré-existante non chiffrée (avant migration) : elle est
            # déjà au format JSON sérialisé, on la décode directement.
            try:
                return json.loads(value)
            except (TypeError, ValueError):
                return value
        return self._from_storage(raw)
