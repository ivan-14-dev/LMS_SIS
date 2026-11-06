"""API tests for stages."""

from datetime import date

from apps.entreprises.models import Entreprise
from apps.etudiants.models import Etudiant
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.stages.models import CandidatureStage, OffreStage
from apps.utilisateurs.models import Utilisateur
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from django.urls import resolve


class StagesAPITestCase(SimpleTestCase):
    """Vérifie que les ViewSets `stages` sont bien routés (et non des stubs morts)."""

    def test_routes_are_registered(self):
        assert resolve("/api/v1/stages/offres-stage/").url_name == "offre-stage-list"
        assert resolve("/api/v1/stages/candidatures-stage/").url_name == "candidature-stage-list"
        assert resolve("/api/v1/stages/conventions-stage/").url_name == "convention-stage-list"


class CandidatureAuthorizationTestCase(TenantAPITestCase):
    def setUp(self):
        entreprise = Entreprise.objects.create(
            raison_sociale="Entreprise test", adresse="1 rue test", code_postal="75000", ville="Paris"
        )
        self.offre = OffreStage.objects.create(
            entreprise=entreprise,
            titre="Stage test",
            type="application",
            description="Stage",
            duree_mois=2,
            date_debut=date(2026, 6, 1),
            date_fin=date(2026, 7, 31),
            date_limite_candidature=date(2026, 5, 1),
            lieu="Paris",
        )
        self.candidatures = []
        for index in range(2):
            user = Utilisateur.objects.create_user(
                f"stage-student-{index}", role="etudiant", etablissement=self.tenant
            )
            etudiant = Etudiant.objects.create(
                universite=self.tenant,
                user=user,
                matricule=f"STAGE-{index}",
                date_naissance=date(2004, 1, 1),
                lieu_naissance="Paris",
                sexe="F",
            )
            self.candidatures.append(
                CandidatureStage.objects.create(
                    etudiant=etudiant, offre=self.offre, lettre_motivation="Motivation", cv="stages/cv/test.pdf"
                )
            )
        self.base = "/api/v1/stages/candidatures-stage/"
        self.offer_applications = f"/api/v1/stages/offres-stage/{self.offre.pk}/candidatures/"

    def test_student_sees_only_own_application_through_both_endpoints(self):
        self.client.force_authenticate(self.candidatures[0].etudiant.user)
        for url in (self.base, self.offer_applications):
            response = self.client.get(url, secure=True)
            assert response.status_code == 200, response.data
            rows = response.data["results"] if url == self.base else response.data
            assert [item["id"] for item in rows] == [self.candidatures[0].pk]
        response = self.client.get(f"{self.base}{self.candidatures[0].pk}/", secure=True)
        assert response.status_code == 200, response.data

    def test_outsider_cannot_read_applications_from_either_endpoint(self):
        outsider = Utilisateur.objects.create_user(
            "stage-outsider", role="enseignant", etablissement=self.tenant
        )
        self.client.force_authenticate(outsider)
        for url in (
            self.base,
            f"{self.base}{self.candidatures[1].pk}/",
            self.offer_applications,
        ):
            response = self.client.get(url, secure=True)
            assert response.status_code == 403, (url, response.data)
        response = self.client.post(
            f"{self.base}{self.candidatures[1].pk}/accepter/", {}, format="json", secure=True
        )
        assert response.status_code == 403, response.data
        self.candidatures[1].refresh_from_db()
        assert self.candidatures[1].statut == "soumise"

    def test_student_cannot_decide_own_or_other_application(self):
        self.client.force_authenticate(self.candidatures[0].etudiant.user)
        for candidature in self.candidatures:
            for decision in ("accepter", "refuser"):
                response = self.client.post(
                    f"{self.base}{candidature.pk}/{decision}/", {}, format="json", secure=True
                )
                assert response.status_code == 403, response.data
                candidature.refresh_from_db()
                assert candidature.statut == "soumise"

    def test_student_cannot_set_decision_or_take_over_another_application(self):
        self.client.force_authenticate(self.candidatures[0].etudiant.user)
        own_url = f"{self.base}{self.candidatures[0].pk}/"
        for payload in (
            {"statut": "acceptee"},
            {"etudiant": self.candidatures[1].etudiant_id},
        ):
            response = self.client.patch(own_url, payload, format="json", secure=True)
            assert response.status_code == 400, response.data
        self.candidatures[0].refresh_from_db()
        assert self.candidatures[0].statut == "soumise"
        assert self.candidatures[0].etudiant_id != self.candidatures[1].etudiant_id
        assert self.client.get(f"{self.base}{self.candidatures[1].pk}/", secure=True).status_code == 404

    def test_student_cannot_create_an_already_accepted_application(self):
        self.client.force_authenticate(self.candidatures[0].etudiant.user)
        response = self.client.post(
            self.base,
            {
                "etudiant": self.candidatures[0].etudiant_id,
                "offre": self.offre.pk,
                "lettre_motivation": "Motivation",
                "cv": SimpleUploadedFile("cv.pdf", b"CV", content_type="application/pdf"),
                "statut": "acceptee",
            },
            secure=True,
        )
        assert response.status_code == 400, response.data
        assert CandidatureStage.objects.count() == 2

    def test_closing_offer_prevents_new_applications_but_open_offer_accepts_them(self):
        applicants = []
        for index in range(2):
            user = Utilisateur.objects.create_user(
                f"stage-lifecycle-{index}", role="etudiant", etablissement=self.tenant
            )
            applicants.append(
                Etudiant.objects.create(
                    universite=self.tenant,
                    user=user,
                    matricule=f"STAGE-LIFECYCLE-{index}",
                    date_naissance=date(2004, 1, 1),
                    lieu_naissance="Paris",
                    sexe="F",
                )
            )

        def apply(applicant, filename):
            self.client.force_authenticate(applicant.user)
            return self.client.post(
                self.base,
                {
                    "etudiant": applicant.pk,
                    "offre": self.offre.pk,
                    "lettre_motivation": "Motivation",
                    "cv": SimpleUploadedFile(filename, b"CV", content_type="application/pdf"),
                },
                secure=True,
            )

        response = apply(applicants[0], "open-offer-cv.pdf")
        assert response.status_code == 201, response.data
        assert CandidatureStage.objects.filter(etudiant=applicants[0], offre=self.offre).exists()

        manager = Utilisateur.objects.create_user(
            "stage-lifecycle-manager", role="scolarite", etablissement=self.tenant
        )
        self.client.force_authenticate(manager)
        response = self.client.post(
            f"/api/v1/stages/offres-stage/{self.offre.pk}/fermer/", {}, format="json", secure=True
        )
        assert response.status_code == 200, response.data
        self.offre.refresh_from_db()
        assert self.offre.statut == "fermee"

        response = apply(applicants[1], "closed-offer-cv.pdf")
        assert response.status_code == 400, response.data
        assert "offre" in response.data
        assert not CandidatureStage.objects.filter(etudiant=applicants[1], offre=self.offre).exists()

    def test_scolarite_and_staff_can_read_and_decide_applications(self):
        managers = (
            Utilisateur.objects.create_user(
                "stage-scolarite", role="scolarite", etablissement=self.tenant
            ),
            Utilisateur.objects.create_user(
                "stage-staff", role="enseignant", is_staff=True, etablissement=self.tenant
            ),
        )
        for manager, candidature, decision, statut in zip(
            managers, self.candidatures, ("accepter", "refuser"), ("acceptee", "refusee")
        ):
            self.client.force_authenticate(manager)
            for url in (self.base, self.offer_applications):
                response = self.client.get(url, secure=True)
                assert response.status_code == 200, response.data
                rows = response.data["results"] if url == self.base else response.data
                assert {item["id"] for item in rows} == {item.pk for item in self.candidatures}
            response = self.client.get(f"{self.base}{candidature.pk}/", secure=True)
            assert response.status_code == 200, response.data
            response = self.client.post(
                f"{self.base}{candidature.pk}/{decision}/", {}, format="json", secure=True
            )
            assert response.status_code == 200, response.data
            candidature.refresh_from_db()
            assert candidature.statut == statut
