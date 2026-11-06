"""API tests for etablissement."""

from datetime import date
from unittest import TestCase

from apps.etablissement.models import AnneeScolaire, Etablissement, Periode
from apps.etablissement.serializers import EtablissementSerializer
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.utilisateurs.models import Utilisateur
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


class AcademicYearDeletionAPITestCase(TenantAPITestCase):
    def setUp(self):
        super().setUp()
        admin = Utilisateur.objects.create_superuser("calendar-admin", etablissement=self.tenant)
        self.client.force_authenticate(admin)
        self.year = AnneeScolaire.objects.create(
            etablissement=self.tenant,
            libelle="2026-2027",
            date_debut=date(2026, 9, 1),
            date_fin=date(2027, 6, 30),
        )
        self.period = Periode.objects.create(
            annee_scolaire=self.year,
            type="trimestre",
            numero=1,
            date_debut=date(2026, 9, 1),
            date_fin=date(2026, 12, 20),
        )

    def test_deleting_year_does_not_cascade_into_closed_period(self):
        closed = self.client.post(f"/api/v1/etablissement/periodes/{self.period.pk}/cloturer/")
        assert closed.status_code == 200, closed.data

        response = self.client.delete(f"/api/v1/etablissement/annees/{self.year.pk}/")

        assert response.status_code == 400, response.data
        assert AnneeScolaire.objects.filter(pk=self.year.pk).exists()
        assert Periode.objects.filter(pk=self.period.pk, cloturee=True).exists()

    def test_deleting_year_with_only_open_periods_still_works(self):
        response = self.client.delete(f"/api/v1/etablissement/annees/{self.year.pk}/")

        assert response.status_code == 204, response.data
        assert not Periode.objects.filter(pk=self.period.pk).exists()
