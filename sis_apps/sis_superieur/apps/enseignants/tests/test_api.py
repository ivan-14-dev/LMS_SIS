"""API tests for enseignants (SIS Supérieur)."""

from apps.enseignants.models import EnseignantChercheur
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.utilisateurs.models import Utilisateur

TEST_USER_PASSWORD = "irrelevant-test-value-not-a-real-secret"


class EnseignantsAPITestCase(TenantAPITestCase):
    """Tests du ViewSet EnseignantChercheur."""

    def setUp(self):
        self.scolarite = Utilisateur.objects.create_user(
            "scolarite_user",
            "scolarite@test.com",
            TEST_USER_PASSWORD,
            role="scolarite",
            etablissement=self.tenant,
        )
        self.enseignant_user = Utilisateur.objects.create_user(
            "mcf_user",
            "mcf@test.com",
            TEST_USER_PASSWORD,
            role="enseignant",
            etablissement=self.tenant,
        )
        self.enseignant = EnseignantChercheur.objects.create(
            user=self.enseignant_user,
            corps="MCF",
            specialite="Informatique",
        )

    def test_list_requires_authentication(self):
        response = self.client.get("/api/v1/enseignants/")
        assert response.status_code == 401

    def test_scolarite_can_list_enseignants(self):
        self.client.force_authenticate(user=self.scolarite)

        response = self.client.get("/api/v1/enseignants/")

        assert response.status_code == 200
        specialites = [item["specialite"] for item in response.data["results"]]
        assert "Informatique" in specialites

    def test_me_returns_own_profile(self):
        self.client.force_authenticate(user=self.enseignant_user)

        response = self.client.get("/api/v1/enseignants/me/")

        assert response.status_code == 200
        assert response.data["specialite"] == "Informatique"

    def test_me_returns_404_for_non_teacher(self):
        self.client.force_authenticate(user=self.scolarite)

        response = self.client.get("/api/v1/enseignants/me/")

        assert response.status_code == 404

    def test_teacher_cannot_update_own_profile(self):
        self.client.force_authenticate(user=self.enseignant_user)

        response = self.client.patch(
            f"/api/v1/enseignants/{self.enseignant.pk}/",
            {"specialite": "Mathématiques"},
        )

        assert response.status_code == 403
