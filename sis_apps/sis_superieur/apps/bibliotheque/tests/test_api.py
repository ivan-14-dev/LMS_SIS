"""API tests for bibliotheque."""

from datetime import timedelta

from apps.bibliotheque.models import Emprunt, Exemplaire, Livre
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.utilisateurs.models import Utilisateur
from django.test import SimpleTestCase
from django.urls import resolve
from django.utils import timezone


class BibliothequeAPITestCase(SimpleTestCase):
    """Vérifie que les ViewSets `bibliotheque` sont bien routés (et non des stubs morts)."""

    def test_routes_are_registered(self):
        assert resolve("/api/v1/bibliotheque/livres/").url_name == "livre-list"
        assert resolve("/api/v1/bibliotheque/exemplaires/").url_name == "exemplaire-list"
        assert resolve("/api/v1/bibliotheque/emprunts/").url_name == "emprunt-list"
        assert (
            resolve("/api/v1/bibliotheque/reservations-bibliotheque/").url_name
            == "reservation-bibliotheque-list"
        )


class EmpruntRenouveleAPITestCase(TenantAPITestCase):
    def setUp(self):
        self.bibliothecaire = Utilisateur.objects.create_user(
            "bibliothecaire-test", role="bibliothecaire", etablissement=self.tenant
        )
        self.emprunteur = Utilisateur.objects.create_user(
            "emprunteur-test", etablissement=self.tenant
        )
        self.client.force_authenticate(self.bibliothecaire)
        self.livre = Livre.objects.create(titre="Livre test", auteurs="Auteur test")
        self.exemplaire = Exemplaire.objects.create(
            livre=self.livre, code_barre="TEST-001"
        )
        self.today = timezone.now().date()
        self.emprunt = Emprunt.objects.create(
            exemplaire=self.exemplaire,
            emprunteur=self.emprunteur,
            date_emprunt=self.today,
            date_retour_prevue=self.today + timedelta(days=7),
        )
        self.emprunt_url = f"/api/v1/bibliotheque/emprunts/{self.emprunt.pk}/"

    def test_renewed_loan_remains_unavailable_and_can_be_returned(self):
        response = self.client.post(f"{self.emprunt_url}renouveler/")
        assert response.status_code == 200, response.data
        self.emprunt.refresh_from_db()
        assert self.emprunt.statut == "renouvele"

        exemplaire = self.client.get(
            f"/api/v1/bibliotheque/exemplaires/{self.exemplaire.pk}/"
        )
        assert exemplaire.status_code == 200, exemplaire.data
        assert exemplaire.data["disponible"] is False
        livre = self.client.get(f"/api/v1/bibliotheque/livres/{self.livre.pk}/")
        assert livre.data["nb_exemplaires_disponibles"] == 0
        livres = self.client.get("/api/v1/bibliotheque/livres/")
        assert livres.data["results"][0]["nb_exemplaires_disponibles"] == 0

        returned = self.client.post(f"{self.emprunt_url}rendre/")
        assert returned.status_code == 200, returned.data
        self.emprunt.refresh_from_db()
        assert self.emprunt.statut == "rendu"
        assert self.client.get(
            f"/api/v1/bibliotheque/exemplaires/{self.exemplaire.pk}/"
        ).data["disponible"] is True

    def test_renewed_overdue_loan_is_reported_and_can_be_renewed_again(self):
        self.emprunt.date_retour_prevue = self.today - timedelta(days=20)
        self.emprunt.save(update_fields=["date_retour_prevue"])

        first = self.client.post(f"{self.emprunt_url}renouveler/")
        assert first.status_code == 200, first.data
        overdue = self.client.get("/api/v1/bibliotheque/emprunts/en_retard/")
        assert overdue.status_code == 200, overdue.data
        assert [loan["id"] for loan in overdue.data] == [self.emprunt.pk]
        assert overdue.data[0]["jours_retard"] == 6

        second = self.client.post(f"{self.emprunt_url}renouveler/")
        assert second.status_code == 200, second.data
        third = self.client.post(f"{self.emprunt_url}renouveler/")
        assert third.status_code == 400
        self.emprunt.refresh_from_db()
        assert self.emprunt.nb_renouvellements == 2
