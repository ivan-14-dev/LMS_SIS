"""API tests for mobilite."""

from datetime import date, timedelta

from apps.etablissement.models import AnneeUniversitaire
from apps.etudiants.models import Etudiant
from apps.formations.models import Formation
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.mobilite.models import CandidatureMobilite, ProgrammeMobilite
from apps.utilisateurs.models import Utilisateur
from django.test import SimpleTestCase
from django.urls import resolve
from django.utils import timezone


class MobiliteAPITestCase(SimpleTestCase):
    """Vérifie que les ViewSets `mobilite` sont bien routés (et non des stubs morts)."""

    def test_routes_are_registered(self):
        assert resolve("/api/v1/mobilite/programmes-mobilite/").url_name == "programme-mobilite-list"
        assert resolve("/api/v1/mobilite/candidatures-mobilite/").url_name == "candidature-mobilite-list"
        assert resolve("/api/v1/mobilite/accords-etudes/").url_name == "accord-etudes-list"


class CandidatureDecisionAPITestCase(TenantAPITestCase):
    def setUp(self):
        self.admin = Utilisateur.objects.create_superuser(
            "mobility-admin", role="super_admin", etablissement=self.tenant
        )
        self.client.force_authenticate(self.admin)
        student_user = Utilisateur.objects.create_user(
            "mobility-student", role="etudiant", etablissement=self.tenant
        )
        etudiant = Etudiant.objects.create(
            universite=self.tenant,
            user=student_user,
            matricule="MOB-001",
            date_naissance=date(2002, 1, 1),
            lieu_naissance="Paris",
            sexe="F",
            adresse="1 rue des Études",
            code_postal="75000",
            ville="Paris",
            telephone="0100000000",
        )
        today = timezone.localdate()
        year = AnneeUniversitaire.objects.create(
            universite=self.tenant,
            libelle=str(today.year),
            date_debut=date(today.year, 1, 1),
            date_fin=date(today.year, 12, 31),
        )
        formation = Formation.objects.create(code="MOB", nom="Licence", type="licence")
        programme = ProgrammeMobilite.objects.create(
            formation=formation,
            nom="Mobilité test",
            type="erasmus",
            universite_accueil="Université partenaire",
            pays="France",
            duree_mois=6,
            date_limite_candidature=today + timedelta(days=30),
            annee_universitaire=year,
        )
        self.candidature = CandidatureMobilite.objects.create(
            etudiant=etudiant,
            programme=programme,
            lettre_motivation="Candidature",
            cv="mobilite/cv/test.pdf",
            releve_notes="mobilite/releves/test.pdf",
            projet_personnel="Étudier à l'étranger",
        )
        self.url = f"/api/v1/mobilite/candidatures-mobilite/{self.candidature.pk}/"

    def test_decision_requires_submission_and_cannot_be_bypassed_by_patch(self):
        response = self.client.post(f"{self.url}decider/", {"decision": "acceptee"})
        assert response.status_code == 400, response.data
        self.candidature.refresh_from_db()
        assert self.candidature.statut == "brouillon"
        assert self.candidature.decision_par_id is None

        response = self.client.patch(
            self.url,
            {
                "statut": "soumise",
                "date_soumission": timezone.now().isoformat(),
                "decision_par": self.admin.pk,
                "motif_refus": "sans décision",
            },
            format="json",
        )
        assert response.status_code == 200, response.data
        self.candidature.refresh_from_db()
        assert self.candidature.statut == "brouillon"
        assert self.candidature.date_soumission is None
        assert self.candidature.decision_par_id is None
        assert self.candidature.motif_refus == ""

        response = self.client.post(f"{self.url}soumettre/")
        assert response.status_code == 200, response.data
        self.candidature.refresh_from_db()
        assert self.candidature.date_soumission is not None

        response = self.client.post(f"{self.url}decider/", {"decision": "preselectionne"})
        assert response.status_code == 200, response.data
        self.candidature.refresh_from_db()
        assert self.candidature.statut == "preselectionne"

        response = self.client.post(f"{self.url}decider/", {"decision": "acceptee"})
        assert response.status_code == 200, response.data
        self.candidature.refresh_from_db()
        assert self.candidature.statut == "acceptee"
        assert self.candidature.decision_par_id == self.admin.pk

        response = self.client.post(f"{self.url}decider/", {"decision": "refusee"})
        assert response.status_code == 400, response.data
        self.candidature.refresh_from_db()
        assert self.candidature.statut == "acceptee"
