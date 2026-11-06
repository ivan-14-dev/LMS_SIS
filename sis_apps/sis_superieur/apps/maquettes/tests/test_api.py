"""API tests for maquettes."""

from datetime import date

from apps.etablissement.models import AnneeUniversitaire
from apps.formations.models import Formation, MaquetteFormation
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.utilisateurs.models import Utilisateur
from django.test import SimpleTestCase
from django.urls import resolve


class MaquettesAPITestCase(SimpleTestCase):
    """Vérifie que le ViewSet `maquettes` est bien routé (et non un stub mort)."""

    def test_routes_are_registered(self):
        assert resolve("/api/v1/maquettes/").url_name == "maquette-list"


class MaquettesAcademicYearTests(TenantAPITestCase):
    def setUp(self):
        self.admin = Utilisateur.objects.create_superuser(
            "maquette-admin", role="super_admin", etablissement=self.tenant
        )
        self.client.force_authenticate(self.admin)
        self.formation = Formation.objects.create(code="MAQ", nom="Licence", type="licence")
        self.first_year = AnneeUniversitaire.objects.create(
            universite=self.tenant,
            libelle="2024-2025",
            date_debut=date(2024, 9, 1),
            date_fin=date(2025, 8, 31),
        )
        self.next_year = AnneeUniversitaire.objects.create(
            universite=self.tenant,
            libelle="2025-2026",
            date_debut=date(2025, 9, 1),
            date_fin=date(2026, 8, 31),
        )
        self.maquette = MaquetteFormation.objects.create(
            formation=self.formation, annee_universitaire=self.first_year
        )
        self.url = f"/api/v1/maquettes/{self.maquette.pk}/"

    def test_cannot_move_a_curriculum_out_of_a_closed_year(self):
        self.first_year.cloturee = True
        self.first_year.save(update_fields=["cloturee"])

        response = self.client.patch(self.url, {"annee_universitaire": self.next_year.pk}, format="json", secure=True)

        assert response.status_code == 400, response.data
        assert "calendrier" in response.data
        self.maquette.refresh_from_db()
        assert self.maquette.annee_universitaire_id == self.first_year.pk

    def test_cannot_move_a_curriculum_into_a_closed_year(self):
        self.next_year.cloturee = True
        self.next_year.save(update_fields=["cloturee"])

        response = self.client.patch(self.url, {"annee_universitaire": self.next_year.pk}, format="json", secure=True)

        assert response.status_code == 400, response.data
        assert "calendrier" in response.data
        self.maquette.refresh_from_db()
        assert self.maquette.annee_universitaire_id == self.first_year.pk

        self.next_year.cloturee = False
        self.next_year.save(update_fields=["cloturee"])
        response = self.client.patch(self.url, {"annee_universitaire": self.next_year.pk}, format="json", secure=True)
        assert response.status_code == 200, response.data
