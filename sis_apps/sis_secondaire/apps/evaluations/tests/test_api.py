"""API tests for evaluations."""

from django.test import SimpleTestCase
from django.urls import resolve


class EvaluationsAPITestCase(SimpleTestCase):
    def test_evaluation_routes_are_registered(self):
        list_match = resolve("/api/v1/evaluations/")
        detail_match = resolve("/api/v1/evaluations/1/")
        notes_match = resolve("/api/v1/evaluations/1/notes/")
        export_match = resolve("/api/v1/evaluations/exporter/")

        self.assertEqual(list_match.url_name, "evaluation-list")
        self.assertEqual(detail_match.url_name, "evaluation-detail")
        self.assertEqual(notes_match.url_name, "evaluation-notes")
        self.assertEqual(export_match.url_name, "evaluation-exporter")
