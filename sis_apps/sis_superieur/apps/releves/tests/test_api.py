"""API tests for releves."""

from django.test import SimpleTestCase
from django.urls import resolve


class RelevesAPITestCase(SimpleTestCase):
    def test_releve_routes_are_registered(self):
        list_match = resolve("/api/v1/releves/")
        detail_match = resolve("/api/v1/releves/1/")
        pdf_match = resolve("/api/v1/releves/1/pdf_officiel/")
        transcript_pdf_match = resolve("/api/v1/releves/transcripts/1/pdf_officiel/")
        attestation_pdf_match = resolve("/api/v1/releves/attestations/1/pdf_officiel/")

        self.assertEqual(list_match.url_name, "releve-list")
        self.assertEqual(detail_match.url_name, "releve-detail")
        self.assertEqual(pdf_match.url_name, "releve-pdf-officiel")
        self.assertEqual(transcript_pdf_match.url_name, "transcript-pdf-officiel")
        self.assertEqual(attestation_pdf_match.url_name, "attestation-pdf-officiel")
