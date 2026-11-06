"""API tests for formations."""

from apps.etablissement.models import AnneeUniversitaire, Universite
from apps.formations.models import Formation, MaquetteFormation
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.utilisateurs.models import Utilisateur
from django.test import SimpleTestCase
from django.urls import resolve
from django_tenants.utils import schema_context


class FormationsAPITestCase(SimpleTestCase):
    def test_formation_history_routes_are_registered(self):
        formation_history = resolve("/api/v1/formations/formations/1/historique/")
        parcours_history = resolve("/api/v1/formations/parcours/1/historique/")
        maquette_history = resolve("/api/v1/formations/maquettes/1/historique/")

        assert formation_history.url_name == "formation-historique"
        assert parcours_history.url_name == "parcours-historique"
        assert maquette_history.url_name == "maquette-historique"


class MaquetteYearTenantAPITests(TenantAPITestCase):
    def setUp(self):
        self.user = Utilisateur.objects.create_user(
            "curriculum_staff", role="scolarite", etablissement=self.tenant
        )
        self.client.force_authenticate(self.user)
        self.formation = Formation.objects.create(code="LINFO", nom="Informatique", type="licence")
        self.own_year = AnneeUniversitaire.objects.create(
            universite=self.tenant, libelle="2026-2027",
            date_debut="2026-09-01", date_fin="2027-08-31",
        )
        other = Universite(
            schema_name=f"foreign_curriculum_{self._testMethodName[-8:]}",
            nom="Autre université", type="universite_publique",
            adresse="1 rue des Tests", code_postal="75000", ville="Paris",
            telephone="0100000000", email="other@example.test",
        )
        other.auto_create_schema = False
        with schema_context("public"):
            other.save()
        self.foreign_year = AnneeUniversitaire.objects.create(
            universite=other, libelle="2026-2027",
            date_debut="2026-09-01", date_fin="2027-08-31",
        )

    def test_create_rejects_another_tenants_year(self):
        response = self.client.post(
            "/api/v1/formations/maquettes/",
            {"formation": self.formation.pk, "annee_universitaire": self.foreign_year.pk},
            format="json",
        )

        assert response.status_code == 400, response.data
        assert "annee_universitaire" in response.data
        assert not MaquetteFormation.objects.filter(formation=self.formation).exists()

    def test_other_maquettes_route_cannot_reassign_year_to_another_tenant(self):
        maquette = MaquetteFormation.objects.create(
            formation=self.formation, annee_universitaire=self.own_year
        )

        response = self.client.patch(
            f"/api/v1/maquettes/{maquette.pk}/",
            {"annee_universitaire": self.foreign_year.pk},
            format="json",
        )

        assert response.status_code == 400, response.data
        assert "annee_universitaire" in response.data
        maquette.refresh_from_db()
        assert maquette.annee_universitaire_id == self.own_year.pk
