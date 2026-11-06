"""API tests for stages."""

from apps.eleves.models import Eleve
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.stages.models import ConventionStage, Entreprise
from apps.utilisateurs.models import Utilisateur
from django.test import SimpleTestCase
from django.urls import resolve


class StagesAPITestCase(SimpleTestCase):
    """Vérifie que les ViewSets `stages` sont bien routés (et non des stubs morts)."""

    def test_routes_are_registered(self):
        assert resolve("/api/v1/stages/entreprises-stage/").url_name == "entreprise-stage-list"
        assert resolve("/api/v1/stages/conventions-stage/").url_name == "convention-stage-list"
        assert resolve("/api/v1/stages/suivis-stage/").url_name == "suivi-stage-list"
        assert resolve("/api/v1/stages/evaluations-stage/").url_name == "evaluation-stage-list"


class ConventionStatusTestCase(TenantAPITestCase):
    def setUp(self):
        manager = Utilisateur.objects.create_superuser(
            "stage-manager", role="super_admin", etablissement=self.tenant
        )
        self.client.force_authenticate(manager)
        pupil = Utilisateur.objects.create_user(
            "stage-pupil", role="eleve", etablissement=self.tenant
        )
        eleve = Eleve.objects.create(
            etablissement=self.tenant,
            user=pupil,
            matricule="STAGE-1",
            date_naissance="2010-01-01",
            lieu_naissance="Paris",
            sexe="F",
            date_inscription="2026-09-01",
        )
        entreprise = Entreprise.objects.create(
            raison_sociale="Entreprise test",
            adresse="1 rue du Stage",
            code_postal="75000",
            ville="Paris",
            telephone="0100000000",
        )
        self.url = "/api/v1/stages/conventions-stage/"
        self.payload = {
            "eleve": eleve.pk,
            "entreprise": entreprise.pk,
            "tuteur_entreprise": "Tuteur entreprise",
            "telephone_tuteur": "0100000000",
            "email_tuteur": "tuteur@example.org",
            "maitre_stage_etablissement": manager.pk,
            "date_debut": "2026-10-01",
            "date_fin": "2026-10-31",
            "duree_heures": 100,
            "missions": "Découverte professionnelle",
            "pdf_path": "conventions/stage.pdf",
        }

    def create_convention(self):
        response = self.client.post(self.url, self.payload, format="json")
        assert response.status_code == 201, response.data
        return f"{self.url}{response.data['id']}/"

    def test_create_and_update_cannot_skip_signature_steps(self):
        response = self.client.post(
            self.url, {**self.payload, "statut": "complete"}, format="json"
        )
        assert response.status_code == 400, response.data
        assert not ConventionStage.objects.exists()

        detail_url = self.create_convention()
        response = self.client.patch(
            detail_url,
            {"statut": "complete", "date_signature_complete": "2026-10-01T10:00:00Z"},
            format="json",
        )
        assert response.status_code == 400, response.data
        convention = ConventionStage.objects.get()
        assert convention.statut == "brouillon"
        assert convention.date_signature_complete is None

        date_only = self.client.patch(
            detail_url, {"date_signature_complete": "2026-10-01T10:00:00Z"}, format="json"
        )
        assert date_only.status_code == 200, date_only.data
        convention.refresh_from_db()
        assert convention.date_signature_complete is None

        for statut in ("signee_etudiant", "signee_entreprise", "signee_etablissement", "complete"):
            signed = self.client.post(f"{detail_url}signer/", {}, format="json")
            assert signed.status_code == 200, signed.data
            convention.refresh_from_db()
            assert convention.statut == statut
        assert convention.date_signature_complete is not None

    def test_in_progress_convention_can_still_be_cancelled(self):
        detail_url = self.create_convention()
        signed = self.client.post(f"{detail_url}signer/", {}, format="json")
        assert signed.status_code == 200, signed.data

        cancelled = self.client.patch(detail_url, {"statut": "annulee"}, format="json")
        assert cancelled.status_code == 200, cancelled.data
        assert ConventionStage.objects.get().statut == "annulee"
        assert self.client.post(f"{detail_url}signer/", {}, format="json").status_code == 400
