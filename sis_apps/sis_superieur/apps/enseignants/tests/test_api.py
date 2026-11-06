"""API tests for enseignants (SIS Supérieur)."""

from apps.enseignants.models import AffectationEnseignement, EnseignantChercheur
from apps.etablissement.models import AnneeUniversitaire, Semestre, Universite
from apps.formations.models import Formation, MaquetteFormation
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.ue_ecue.models import UE
from apps.utilisateurs.models import Utilisateur
from django_tenants.utils import schema_context

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


class AffectationsAPITestCase(TenantAPITestCase):
    def setUp(self):
        year = AnneeUniversitaire.objects.create(
            universite=self.tenant, libelle="2026-2027",
            date_debut="2026-09-01", date_fin="2027-08-31",
        )
        semester = Semestre.objects.create(
            annee_universitaire=year, numero=1, type="impair",
            date_debut="2026-09-01", date_fin="2027-01-31",
        )
        formation = Formation.objects.create(nom="Informatique", code="INFO", type="licence")
        maquette = MaquetteFormation.objects.create(formation=formation, annee_universitaire=year)
        ue = UE.objects.create(maquette=maquette, semestre=semester, code="INFO1", nom="Informatique", credits_ects=6)
        self.teacher_user = Utilisateur.objects.create_user(
            "teacher", role="enseignant", etablissement=self.tenant
        )
        other_user = Utilisateur.objects.create_user(
            "other_teacher", role="enseignant", etablissement=self.tenant
        )
        self.scolarite = Utilisateur.objects.create_user(
            "scolarite", role="scolarite", etablissement=self.tenant
        )
        teacher = EnseignantChercheur.objects.create(user=self.teacher_user, specialite="Informatique")
        other = EnseignantChercheur.objects.create(user=other_user, specialite="Mathématiques")
        self.own = AffectationEnseignement.objects.create(
            enseignant=teacher, ue=ue, annee_universitaire=year, type_enseignement="CM", heures=12,
        )
        self.foreign = AffectationEnseignement.objects.create(
            enseignant=other, ue=ue, annee_universitaire=year, type_enseignement="TD", heures=18,
        )

    def _foreign_year(self):
        other = Universite(schema_name=f"enseignants_{self._testMethodName[-12:]}")
        self.setup_tenant(other)
        other.auto_create_schema = False
        with schema_context("public"):
            other.save()
        return AnneeUniversitaire.objects.create(
            universite=other, libelle="2026-2027",
            date_debut="2026-09-01", date_fin="2027-08-31",
        )

    def test_teacher_only_sees_own_assignments(self):
        self.client.force_authenticate(user=self.teacher_user)

        response = self.client.get("/api/v1/enseignants/affectations/")
        assert response.status_code == 200
        assert [item["id"] for item in response.data["results"]] == [self.own.pk]
        assert self.client.get(f"/api/v1/enseignants/affectations/{self.own.pk}/").status_code == 200
        assert self.client.get(f"/api/v1/enseignants/affectations/{self.foreign.pk}/").status_code == 404

    def test_scolarite_can_still_see_all_assignments(self):
        self.client.force_authenticate(user=self.scolarite)

        response = self.client.get("/api/v1/enseignants/affectations/")
        assert response.status_code == 200
        assert {item["id"] for item in response.data["results"]} == {self.own.pk, self.foreign.pk}
        assert self.client.get(f"/api/v1/enseignants/affectations/{self.foreign.pk}/").status_code == 200

    def test_staff_cannot_read_or_modify_another_university_assignment(self):
        foreign_assignment = AffectationEnseignement.objects.create(
            enseignant=self.own.enseignant,
            annee_universitaire=self._foreign_year(),
            type_enseignement="CM",
            heures=20,
        )
        self.client.force_authenticate(user=self.scolarite)
        url = f"/api/v1/enseignants/affectations/{foreign_assignment.pk}/"

        response = self.client.get("/api/v1/enseignants/affectations/")
        assert response.status_code == 200
        assert {item["id"] for item in response.data["results"]} == {self.own.pk, self.foreign.pk}
        assert self.client.get(url).status_code == 404
        teacher_url = f"/api/v1/enseignants/{self.own.enseignant_id}/"
        assignments = self.client.get(f"{teacher_url}affectations/")
        assert assignments.status_code == 200
        assert [item["id"] for item in assignments.data] == [self.own.pk]
        workload = self.client.get(f"{teacher_url}heures_total/")
        assert workload.status_code == 200
        assert workload.data["heures_affectees"] == 12
        assert self.client.patch(url, {"heures": "40.00"}, format="json").status_code == 404
        assert self.client.delete(url).status_code == 404
        foreign_assignment.refresh_from_db()
        assert foreign_assignment.heures == 20

    def test_staff_cannot_allocate_to_another_university_year(self):
        foreign_year = self._foreign_year()
        self.client.force_authenticate(user=self.scolarite)
        url = "/api/v1/enseignants/affectations/"
        payload = {
            "enseignant": self.own.enseignant_id,
            "ue": self.own.ue_id,
            "type_enseignement": "TD",
            "heures": "12.00",
            "annee_universitaire": foreign_year.pk,
        }

        create = self.client.post(url, payload, format="json")
        assert create.status_code == 400
        assert "annee_universitaire" in create.data
        assert not AffectationEnseignement.objects.filter(annee_universitaire=foreign_year).exists()

        update = self.client.patch(
            f"{url}{self.own.pk}/",
            {"annee_universitaire": foreign_year.pk},
            format="json",
        )
        assert update.status_code == 400
        assert "annee_universitaire" in update.data
        self.own.refresh_from_db()
        assert self.own.annee_universitaire.universite_id == self.tenant.pk

        payload["annee_universitaire"] = self.own.annee_universitaire_id
        assert self.client.post(url, payload, format="json").status_code == 201
