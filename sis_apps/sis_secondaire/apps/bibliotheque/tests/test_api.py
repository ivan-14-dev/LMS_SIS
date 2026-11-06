"""API tests for bibliotheque."""

from django.test import SimpleTestCase
from django.urls import resolve

from apps.bibliotheque.models import Exemplaire, Livre
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.utilisateurs.models import Utilisateur


class BibliothequeAPITestCase(SimpleTestCase):
    """Vérifie que les ViewSets `bibliotheque` sont bien routés (et non des stubs morts)."""

    def test_routes_are_registered(self):
        assert resolve("/api/v1/bibliotheque/livres/").url_name == "livre-list"
        assert resolve("/api/v1/bibliotheque/exemplaires/").url_name == "exemplaire-list"
        assert resolve("/api/v1/bibliotheque/emprunts/").url_name == "emprunt-list"


class ExemplaireAvailabilityAPITestCase(TenantAPITestCase):
    def test_unusable_copies_are_not_available_without_active_loans(self):
        user = Utilisateur.objects.create_user(
            "library-reader", role="eleve", etablissement=self.tenant
        )
        self.client.force_authenticate(user)
        livre = Livre.objects.create(titre="Livre de test", auteurs="Auteur de test")

        for etat in ("perdu", "détérioré"):
            with self.subTest(etat=etat):
                exemplaire = Exemplaire.objects.create(
                    livre=livre, code_barre=f"EX-{etat}", etat=etat
                )
                response = self.client.get(
                    f"/api/v1/bibliotheque/exemplaires/{exemplaire.pk}/"
                )
                assert response.status_code == 200, response.data
                assert response.data["disponible"] is False
