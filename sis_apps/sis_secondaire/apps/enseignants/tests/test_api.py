"""API tests for enseignants (SIS Secondaire)."""

import datetime

from apps.classes.models import Classe, Matiere
from apps.enseignants.models import AffectationEnseignant, Personnel
from apps.etablissement.models import AnneeScolaire, Niveau
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

    def test_created_teacher_can_authenticate_in_the_institution(self):
        self.direction.is_superuser = True
        self.direction.save()
        self.client.force_authenticate(self.direction)
        data = {
            "username": "new-teacher",
            "email": "teacher@example.test",
            "first_name": "New",
            "last_name": "Teacher",
            "password": TEST_USER_PASSWORD,
            "date_embauche": "2026-09-01",
        }
        response = self.client.post("/api/v1/enseignants/personnel/", data, format="json")
        assert response.status_code == 201, response.data
        user = Utilisateur.objects.get(username="new-teacher")
        assert user.etablissement == self.tenant
        assert user.check_password(TEST_USER_PASSWORD)
        assert Personnel.objects.filter(user=user).exists()
        assert self.client.post("/api/v1/enseignants/personnel/", data, format="json").status_code == 400

    def test_affectation_rejects_class_from_another_school_year(self):
        year = AnneeScolaire.objects.create(
            etablissement=self.tenant, libelle="2026-2027",
            date_debut="2026-09-01", date_fin="2027-07-01",
        )
        next_year = AnneeScolaire.objects.create(
            etablissement=self.tenant, libelle="2027-2028",
            date_debut="2027-09-01", date_fin="2028-07-01",
        )
        level = Niveau.objects.create(etablissement=self.tenant, code="6e", libelle="Sixième")
        current_class = Classe.objects.create(
            etablissement=self.tenant, annee_scolaire=year, niveau=level, nom="6A"
        )
        next_class = Classe.objects.create(
            etablissement=self.tenant, annee_scolaire=next_year, niveau=level, nom="6A"
        )
        subject = Matiere.objects.create(etablissement=self.tenant, code="MATH", nom="Mathématiques")
        payload = {
            "enseignant": self.personnel.pk,
            "matiere": subject.pk,
            "annee_scolaire": year.pk,
            "classes": [next_class.pk],
            "heures_semaine": "4.00",
        }
        self.client.force_authenticate(user=self.direction)
        url = "/api/v1/enseignants/affectations/"

        rejected = self.client.post(url, payload, format="json")
        assert rejected.status_code == 400, rejected.data
        assert "classes" in rejected.data
        assert not AffectationEnseignant.objects.exists()

        created = self.client.post(url, {**payload, "classes": [current_class.pk]}, format="json")
        assert created.status_code == 201, created.data
        assignment = AffectationEnseignant.objects.get(pk=created.data["id"])
        detail_url = f"{url}{assignment.pk}/"

        rejected = self.client.patch(detail_url, {"classes": [next_class.pk]}, format="json")
        assert rejected.status_code == 400, rejected.data
        assert "classes" in rejected.data

        rejected = self.client.patch(detail_url, {"annee_scolaire": next_year.pk}, format="json")
        assert rejected.status_code == 400, rejected.data
        assert "classes" in rejected.data
        assignment.refresh_from_db()
        assert assignment.annee_scolaire_id == year.pk
        assert list(assignment.classes.values_list("pk", flat=True)) == [current_class.pk]
