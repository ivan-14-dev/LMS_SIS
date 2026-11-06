"""API tests for releves."""

from unittest.mock import patch

from apps.etablissement.models import AnneeUniversitaire
from apps.etudiants.models import Etudiant
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.releves.models import Transcript
from apps.utilisateurs.models import Utilisateur
from django.test import SimpleTestCase
from django.urls import resolve
from django.utils import timezone


class RelevesAPITestCase(SimpleTestCase):
    def test_releve_routes_are_registered(self):
        list_match = resolve("/api/v1/releves/")
        detail_match = resolve("/api/v1/releves/1/")
        pdf_match = resolve("/api/v1/releves/1/pdf_officiel/")
        history_match = resolve("/api/v1/releves/1/historique/")
        transcript_pdf_match = resolve("/api/v1/releves/transcripts/1/pdf_officiel/")
        transcript_history_match = resolve("/api/v1/releves/transcripts/1/historique/")
        attestation_pdf_match = resolve("/api/v1/releves/attestations/1/pdf_officiel/")
        attestation_history_match = resolve("/api/v1/releves/attestations/1/historique/")

        assert list_match.url_name == "releve-list"
        assert detail_match.url_name == "releve-detail"
        assert pdf_match.url_name == "releve-pdf-officiel"
        assert history_match.url_name == "releve-historique"
        assert transcript_pdf_match.url_name == "transcript-pdf-officiel"
        assert transcript_history_match.url_name == "transcript-historique"
        assert attestation_pdf_match.url_name == "attestation-pdf-officiel"
        assert attestation_history_match.url_name == "attestation-historique"


class TranscriptPublicationTestCase(TenantAPITestCase):
    def setUp(self):
        super().setUp()
        self.staff = Utilisateur.objects.create_user(
            username="transcript-staff", role="scolarite", etablissement=self.tenant
        )
        student_user = Utilisateur.objects.create_user(
            username="transcript-student", role="etudiant", etablissement=self.tenant
        )
        self.student = Etudiant.objects.create(
            user=student_user,
            universite=self.tenant,
            matricule="TRANSCRIPT-01",
            date_naissance="2000-01-01",
        )
        self.year = AnneeUniversitaire.objects.create(
            universite=self.tenant,
            libelle="2024-2025",
            date_debut="2024-09-01",
            date_fin="2025-08-31",
        )
        self.transcript = Transcript.objects.create(
            etudiant=self.student,
            pdf_path="transcripts/draft.pdf",
            credits_total=60,
            credits_valides=60,
            date_emission=timezone.localdate(),
            numero_serie="TRANSCRIPT-01",
        )
        self.transcript.annees.add(self.year)
        self.client.force_authenticate(self.staff)

    def sign_transcript(self):
        with patch("sis_common.document_policies.requires_financial_clearance", return_value=True), patch(
            "sis_common.document_policies.subject_has_financial_clearance", return_value=True
        ):
            response = self.client.post(f"/api/v1/releves/transcripts/{self.transcript.pk}/signer/")
        assert response.status_code == 200, response.data

    def test_crud_cannot_publish_unsigned_transcripts_or_bypass_signature_gate(self):
        url = f"/api/v1/releves/transcripts/{self.transcript.pk}/"
        with patch("sis_common.document_policies.requires_financial_clearance", return_value=True), patch(
            "sis_common.document_policies.subject_has_financial_clearance", return_value=False
        ):
            response = self.client.post(f"{url}signer/")
        assert response.status_code == 409, response.data

        response = self.client.patch(
            url, {"credits_total": "61.00", "signe_par": self.staff.pk}, format="json"
        )
        assert response.status_code == 200, response.data
        self.transcript.refresh_from_db()
        assert self.transcript.signe_par_id is None
        assert self.transcript.credits_total == 61

        response = self.client.post(
            "/api/v1/releves/transcripts/",
            {
                "etudiant": self.student.pk,
                "annees": [self.year.pk],
                "pdf_path": "transcripts/another-draft.pdf",
                "credits_total": "60",
                "credits_valides": "60",
                "date_emission": timezone.localdate().isoformat(),
                "numero_serie": "TRANSCRIPT-02",
                "signe_par": self.staff.pk,
            },
            format="json",
        )
        assert response.status_code == 201, response.data
        assert Transcript.objects.get(numero_serie="TRANSCRIPT-02").signe_par_id is None

        self.client.force_authenticate(self.student.user)
        assert self.client.get(url).status_code == 404
        assert self.client.get(f"{url}pdf_officiel/").status_code == 404
        assert self.client.get("/api/v1/releves/transcripts/mes_transcripts/").data == []

    def test_signed_transcript_cannot_be_tampered_with_or_deleted(self):
        url = f"/api/v1/releves/transcripts/{self.transcript.pk}/"
        self.sign_transcript()

        assert self.client.patch(url, {"credits_total": "90.00"}, format="json").status_code == 400
        assert self.client.patch(url, {"annees": []}, format="json").status_code == 400
        assert self.client.put(
            url,
            {
                "etudiant": self.student.pk,
                "annees": [],
                "pdf_path": "transcripts/altered.pdf",
                "credits_total": "90.00",
                "credits_valides": "60.00",
                "date_emission": timezone.localdate().isoformat(),
                "numero_serie": "TRANSCRIPT-01",
            },
            format="json",
        ).status_code == 400
        assert self.client.delete(url).status_code == 400

        self.transcript.refresh_from_db()
        assert self.transcript.credits_total == 60
        assert self.transcript.pdf_path == "transcripts/draft.pdf"
        assert list(self.transcript.annees.values_list("pk", flat=True)) == [self.year.pk]
        assert self.transcript.signe_par_id == self.staff.pk
        history = self.client.get(f"{url}historique/")
        assert history.status_code == 200
        assert len(history.data) == 1

    def test_signed_transcript_is_published_without_allowing_replay_or_foreign_role(self):
        url = f"/api/v1/releves/transcripts/{self.transcript.pk}/"
        self.client.force_authenticate(self.student.user)
        assert self.client.post(f"{url}signer/").status_code == 403
        self.client.force_authenticate(self.staff)
        self.sign_transcript()
        with patch("sis_common.document_policies.requires_financial_clearance", return_value=True), patch(
            "sis_common.document_policies.subject_has_financial_clearance", return_value=True
        ):
            assert self.client.post(f"{url}signer/").status_code == 400

        self.client.force_authenticate(self.student.user)
        response = self.client.get(f"{url}pdf_officiel/")
        assert response.status_code == 200
        assert response["Content-Type"] == "application/pdf"
        assert self.client.get(url).status_code == 200

        other_user = Utilisateur.objects.create_user(
            username="transcript-other-student", role="etudiant", etablissement=self.tenant
        )
        Etudiant.objects.create(
            user=other_user,
            universite=self.tenant,
            matricule="TRANSCRIPT-OTHER",
            date_naissance="2000-01-01",
        )
        self.client.force_authenticate(other_user)
        assert self.client.get(f"{url}pdf_officiel/").status_code == 404
        assert self.client.post(f"{url}signer/").status_code == 403
