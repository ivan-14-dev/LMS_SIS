"""API tests for recherche."""

from datetime import date

from apps.enseignants.models import EnseignantChercheur
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.recherche.models import Laboratoire, ProjetRecherche
from apps.utilisateurs.models import Utilisateur
from django.test import SimpleTestCase
from django.urls import resolve


class RechercheAPITestCase(SimpleTestCase):
    """Vérifie que les ViewSets `recherche` sont bien routés (et non des stubs morts)."""

    def test_routes_are_registered(self):
        assert resolve("/api/v1/recherche/laboratoires/").url_name == "laboratoire-list"
        assert resolve("/api/v1/recherche/projets-recherche/").url_name == "projet-recherche-list"
        assert (
            resolve("/api/v1/recherche/productions-scientifiques/").url_name
            == "production-scientifique-list"
        )
        assert resolve("/api/v1/recherche/theses/").url_name == "these-list"


class ProjetRechercheStatusAPITestCase(TenantAPITestCase):
    def setUp(self):
        manager = Utilisateur.objects.create_superuser(
            "research-manager", etablissement=self.tenant
        )
        researcher = Utilisateur.objects.create_user(
            "researcher", etablissement=self.tenant
        )
        self.client.force_authenticate(manager)
        self.responsable = EnseignantChercheur.objects.create(
            user=researcher, specialite="Sciences"
        )
        self.laboratoire = Laboratoire.objects.create(nom="Laboratoire", acronyme="LAB")
        self.projet = ProjetRecherche.objects.create(
            laboratoire=self.laboratoire,
            responsable=self.responsable,
            titre="Projet de test",
            description="Description du projet",
            date_debut=date(2026, 1, 1),
            date_fin=date(2027, 1, 1),
            statut="propose",
        )
        self.url = f"/api/v1/recherche/projets-recherche/{self.projet.pk}/"

    def test_terminer_requires_project_in_progress(self):
        rejected = self.client.post(f"{self.url}terminer/", {}, format="json")
        assert rejected.status_code == 400, rejected.data
        self.projet.refresh_from_db()
        assert self.projet.statut == "propose"

        self.projet.statut = "en_cours"
        self.projet.save(update_fields=["statut"])
        completed = self.client.post(f"{self.url}terminer/", {}, format="json")
        assert completed.status_code == 200, completed.data
        self.projet.refresh_from_db()
        assert self.projet.statut == "termine"

    def test_direct_patch_cannot_bypass_termination_rule(self):
        rejected = self.client.patch(self.url, {"statut": "termine"}, format="json")
        assert rejected.status_code == 400, rejected.data
        self.projet.refresh_from_db()
        assert self.projet.statut == "propose"

        self.projet.statut = "en_cours"
        self.projet.save(update_fields=["statut"])
        completed = self.client.patch(self.url, {"statut": "termine"}, format="json")
        assert completed.status_code == 200, completed.data
        self.projet.refresh_from_db()
        assert self.projet.statut == "termine"

    def test_direct_create_cannot_start_as_completed(self):
        response = self.client.post(
            "/api/v1/recherche/projets-recherche/",
            {
                "titre": "Projet non démarré",
                "description": "Description du projet",
                "laboratoire": self.laboratoire.pk,
                "responsable": self.responsable.pk,
                "date_debut": "2026-01-01",
                "date_fin": "2027-01-01",
                "statut": "termine",
            },
            format="json",
        )
        assert response.status_code == 400, response.data
        assert not ProjetRecherche.objects.filter(titre="Projet non démarré").exists()
