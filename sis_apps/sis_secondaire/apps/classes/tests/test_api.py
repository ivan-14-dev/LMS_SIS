"""API tests for classes."""

import datetime

from apps.classes.models import Classe, Groupe
from apps.etablissement.models import AnneeScolaire, Niveau
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.utilisateurs.models import Utilisateur
from django.test import SimpleTestCase
from django.urls import resolve


class ClassesAPITestCase(SimpleTestCase):
    def test_class_history_route_is_registered(self):
        history_match = resolve("/api/v1/classes/classes/1/historique/")
        assert history_match.url_name == "classe-historique"


class GroupeAcademicYearTestCase(TenantAPITestCase):
    def setUp(self):
        admin = Utilisateur.objects.create_superuser(
            "groupe-year-admin", role="super_admin", etablissement=self.tenant
        )
        self.client.force_authenticate(admin)
        self.first_year = AnneeScolaire.objects.create(
            etablissement=self.tenant,
            libelle="2026-2027",
            date_debut=datetime.date(2026, 9, 1),
            date_fin=datetime.date(2027, 6, 30),
        )
        self.next_year = AnneeScolaire.objects.create(
            etablissement=self.tenant,
            libelle="2027-2028",
            date_debut=datetime.date(2027, 9, 1),
            date_fin=datetime.date(2028, 6, 30),
        )
        niveau = Niveau.objects.create(etablissement=self.tenant, code="6e", libelle="Sixième")
        self.first_class = Classe.objects.create(
            etablissement=self.tenant, annee_scolaire=self.first_year, niveau=niveau, nom="6A"
        )
        self.next_class = Classe.objects.create(
            etablissement=self.tenant, annee_scolaire=self.next_year, niveau=niveau, nom="6A"
        )

    def test_create_rejects_class_from_another_year(self):
        url = "/api/v1/classes/groupes/"
        payload = {
            "etablissement": self.tenant.pk,
            "annee_scolaire": self.first_year.pk,
            "nom": "Langue A",
            "type": "langue",
            "classes": [self.next_class.pk],
        }

        response = self.client.post(url, payload, format="json", secure=True)
        assert response.status_code == 400, response.data
        assert "classes" in response.data
        assert not Groupe.objects.filter(nom="Langue A").exists()

        response = self.client.post(
            url, {**payload, "classes": [self.first_class.pk]}, format="json", secure=True
        )
        assert response.status_code == 201, response.data
        assert list(Groupe.objects.get(pk=response.data["id"]).classes.all()) == [self.first_class]

    def test_patch_rejects_cross_year_classes_and_year_change_without_reassignment(self):
        groupe = Groupe.objects.create(
            etablissement=self.tenant, annee_scolaire=self.first_year, nom="Langue A", type="langue"
        )
        groupe.classes.add(self.first_class)
        url = f"/api/v1/classes/groupes/{groupe.pk}/"

        for payload in (
            {"annee_scolaire": self.next_year.pk},
            {"classes": [self.next_class.pk]},
        ):
            response = self.client.patch(url, payload, format="json", secure=True)
            assert response.status_code == 400, response.data
            assert "classes" in response.data
            groupe.refresh_from_db()
            assert groupe.annee_scolaire_id == self.first_year.pk
            assert list(groupe.classes.all()) == [self.first_class]

        response = self.client.patch(
            url,
            {"annee_scolaire": self.next_year.pk, "classes": [self.next_class.pk]},
            format="json",
            secure=True,
        )
        assert response.status_code == 200, response.data
        groupe.refresh_from_db()
        assert groupe.annee_scolaire_id == self.next_year.pk
        assert list(groupe.classes.all()) == [self.next_class]
