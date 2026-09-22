"""API tests for etablissement."""

from unittest import TestCase

from apps.etablissement.models import Etablissement
from apps.etablissement.serializers import EtablissementSerializer
from django.urls import resolve


class EtablissementConfigurationSerializerTestCase(TestCase):
    def setUp(self):
        self.etablissement = Etablissement(
            nom="École test",
            type="college",
            fonctionnalites={"cours_en_ligne": True},
            configuration_visio={"provider": "none", "public_url": ""},
        )

    def test_partial_feature_update_preserves_defaults(self):
        serializer = EtablissementSerializer(
            self.etablissement,
            data={"fonctionnalites": {"classes_virtuelles": True}},
            partial=True,
        )

        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data["fonctionnalites"]["cours_en_ligne"]
        assert serializer.validated_data["fonctionnalites"]["classes_virtuelles"]

    def test_current_establishment_route_is_exposed(self):
        assert resolve("/api/v1/etablissement/current/").url_name == "current"

    def test_custom_type_requires_a_label(self):
        serializer = EtablissementSerializer(
            self.etablissement,
            data={"type": "autre", "type_personnalise": ""},
            partial=True,
        )

        assert not serializer.is_valid()
        assert "type_personnalise" in serializer.errors

    def test_live_configuration_rejects_insecure_url(self):
        serializer = EtablissementSerializer(
            self.etablissement,
            data={
                "configuration_visio": {
                    "provider": "bigbluebutton",
                    "public_url": "http://classes.example.edu",
                }
            },
            partial=True,
        )

        assert not serializer.is_valid()
        assert "configuration_visio" in serializer.errors
