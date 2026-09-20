"""API tests for etablissement."""

from unittest import TestCase

from apps.etablissement.models import Universite
from apps.etablissement.serializers import UniversiteSerializer
from django.urls import resolve


class UniversiteConfigurationSerializerTestCase(TestCase):
    def setUp(self):
        self.universite = Universite(
            nom="Université test",
            type="institut",
            fonctionnalites={"cours_en_ligne": True},
            configuration_visio={"provider": "none", "public_url": ""},
        )

    def test_partial_feature_update_preserves_defaults(self):
        serializer = UniversiteSerializer(
            self.universite,
            data={"fonctionnalites": {"classes_virtuelles": True}},
            partial=True,
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertTrue(serializer.validated_data["fonctionnalites"]["cours_en_ligne"])
        self.assertTrue(
            serializer.validated_data["fonctionnalites"]["classes_virtuelles"]
        )

    def test_current_establishment_route_is_exposed(self):
        self.assertEqual(
            resolve("/api/v1/etablissement/current/").url_name,
            "current",
        )

    def test_custom_type_requires_a_label(self):
        serializer = UniversiteSerializer(
            self.universite,
            data={"type": "autre", "type_personnalise": ""},
            partial=True,
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("type_personnalise", serializer.errors)

    def test_live_configuration_rejects_credentials(self):
        serializer = UniversiteSerializer(
            self.universite,
            data={
                "configuration_visio": {
                    "provider": "other_lti",
                    "public_url": "https://alice@classes.example.edu",
                }
            },
            partial=True,
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("configuration_visio", serializer.errors)
