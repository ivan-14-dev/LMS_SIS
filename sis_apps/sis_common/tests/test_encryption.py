"""Tests for the Fernet-based encrypted-at-rest model fields in sis_common."""

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings

from sis_common.encryption import (
    EncryptedCharField,
    EncryptedJSONField,
    EncryptedTextField,
    decrypt_value,
    encrypt_value,
)

TEST_KEY = "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA="


class EncryptValueTests(SimpleTestCase):
    @override_settings(FIELD_ENCRYPTION_KEY=TEST_KEY)
    def test_encrypt_then_decrypt_roundtrips(self):
        token = encrypt_value("FR7630006000011234567890189")
        self.assertNotIn("FR76", token)
        self.assertEqual(decrypt_value(token), "FR7630006000011234567890189")

    def test_missing_key_raises_improperly_configured(self):
        with override_settings(FIELD_ENCRYPTION_KEY=None):
            with self.assertRaises(ImproperlyConfigured):
                encrypt_value("secret")


@override_settings(FIELD_ENCRYPTION_KEY=TEST_KEY)
class EncryptedCharFieldTests(SimpleTestCase):
    def setUp(self):
        self.field = EncryptedCharField(max_length=50, blank=True)

    def test_get_prep_value_encrypts(self):
        stored = self.field.get_prep_value("XYZ-SECRET")
        self.assertNotEqual(stored, "XYZ-SECRET")
        self.assertEqual(self.field.from_db_value(stored, None, None), "XYZ-SECRET")

    def test_blank_value_is_not_encrypted(self):
        self.assertEqual(self.field.get_prep_value(""), "")
        self.assertEqual(self.field.get_prep_value(None), None)

    def test_legacy_plaintext_value_is_returned_unchanged(self):
        # Data written before encryption was introduced is not a valid Fernet
        # token; from_db_value must not raise nor discard the value.
        self.assertEqual(self.field.from_db_value("legacy-plaintext", None, None), "legacy-plaintext")

    def test_db_type_is_text(self):
        self.assertEqual(self.field.db_type(connection=None), "text")


@override_settings(FIELD_ENCRYPTION_KEY=TEST_KEY)
class EncryptedTextFieldTests(SimpleTestCase):
    def test_roundtrip(self):
        field = EncryptedTextField(blank=True)
        stored = field.get_prep_value("Observations cliniques confidentielles")
        self.assertNotIn("confidentielles", stored)
        self.assertEqual(
            field.from_db_value(stored, None, None),
            "Observations cliniques confidentielles",
        )


@override_settings(FIELD_ENCRYPTION_KEY=TEST_KEY)
class EncryptedJSONFieldTests(SimpleTestCase):
    def setUp(self):
        self.field = EncryptedJSONField(default=list, blank=True)

    def test_roundtrip_list(self):
        stored = self.field.get_prep_value(["arachides", "pollen"])
        self.assertIsInstance(stored, str)
        self.assertNotIn("arachides", stored)
        self.assertEqual(
            self.field.from_db_value(stored, None, None), ["arachides", "pollen"]
        )

    def test_legacy_plaintext_json_is_decoded(self):
        # Column previously stored plain JSON text; must still decode.
        self.assertEqual(
            self.field.from_db_value('["arachides"]', None, None), ["arachides"]
        )

    def test_none_returns_default(self):
        self.assertEqual(self.field.from_db_value(None, None, None), [])
