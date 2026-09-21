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

        assert list_match.url_name == "releve-list"
        assert detail_match.url_name == "releve-detail"
        assert pdf_match.url_name == "releve-pdf-officiel"
        assert history_match.url_name == "releve-historique"
        assert transcript_pdf_match.url_name == "transcript-pdf-officiel"
        assert transcript_history_match.url_name == "transcript-historique"
        assert attestation_pdf_match.url_name == "attestation-pdf-officiel"
        assert attestation_history_match.url_name == "attestation-historique"
