"""API tests for enseignants (SIS Secondaire)."""

import datetime

from apps.enseignants.models import Personnel
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.utilisateurs.models import Utilisateur

TEST_USER_PASSWORD = "irrelevant-test-value-not-a-real-secret"


class PersonnelAPITestCase(TenantAPITestCase):
    """Tests du ViewSet Personnel (enseignants/personnel administratif)."""

    def setUp(self):
        self.direction = Utilisateur.objects.create_user(
            "direction_user",
            "direction@test.com",
            TEST_USER_PASSWORD,
            role="direction",
            etablissement=self.tenant,
        )
        self.enseignant_user = Utilisateur.objects.create_user(
            "prof_user",
            "prof@test.com",
            TEST_USER_PASSWORD,
            role="enseignant",
            etablissement=self.tenant,
        )
        self.personnel = Personnel.objects.create(
            user=self.enseignant_user,
            matricule="ENS-0001",
            statut="titulaire",
            date_embauche=datetime.date(2020, 9, 1),
            corps="Certifié",
        )

    def test_list_requires_authentication(self):
        response = self.client.get("/api/v1/enseignants/personnel/")
        assert response.status_code == 401

    def test_direction_can_list_personnel(self):
        self.client.force_authenticate(user=self.direction)

        response = self.client.get("/api/v1/enseignants/personnel/")

        assert response.status_code == 200
        matricules = [item["matricule"] for item in response.data["results"]]
        assert "ENS-0001" in matricules

    def test_me_returns_own_profile_for_teacher(self):
        self.client.force_authenticate(user=self.enseignant_user)

        response = self.client.get("/api/v1/enseignants/personnel/me/")

        assert response.status_code == 200
        assert response.data["matricule"] == "ENS-0001"

    def test_me_returns_404_for_non_personnel_user(self):
        self.client.force_authenticate(user=self.direction)

        response = self.client.get("/api/v1/enseignants/personnel/me/")

        assert response.status_code == 404

    def test_teacher_cannot_update_personnel(self):
        self.client.force_authenticate(user=self.enseignant_user)

        response = self.client.patch(
            f"/api/v1/enseignants/personnel/{self.personnel.pk}/",
            {"corps": "Agrégé"},
        )

        assert response.status_code == 403
