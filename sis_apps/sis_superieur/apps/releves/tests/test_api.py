"""API tests for releves."""

from django.test import SimpleTestCase
from django.urls import resolve


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

        self.assertEqual(list_match.url_name, "releve-list")
        self.assertEqual(detail_match.url_name, "releve-detail")
        self.assertEqual(pdf_match.url_name, "releve-pdf-officiel")
        self.assertEqual(history_match.url_name, "releve-historique")
        self.assertEqual(transcript_pdf_match.url_name, "transcript-pdf-officiel")
        self.assertEqual(transcript_history_match.url_name, "transcript-historique")
        self.assertEqual(attestation_pdf_match.url_name, "attestation-pdf-officiel")
        self.assertEqual(attestation_history_match.url_name, "attestation-historique")
