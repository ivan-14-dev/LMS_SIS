"""API tests for core."""

from django.test import SimpleTestCase
from django.urls import resolve


class CoreAPITestCase(SimpleTestCase):
    def test_workflow_event_routes_are_registered(self):
        list_match = resolve("/api/v1/core/workflow-events/")
        summary_match = resolve("/api/v1/core/workflow-events/bilan/")
        export_match = resolve("/api/v1/core/workflow-events/exporter/")

        self.assertEqual(list_match.url_name, "workflow-event-list")
        self.assertEqual(summary_match.url_name, "workflow-event-bilan")
        self.assertEqual(export_match.url_name, "workflow-event-exporter")

    def test_notification_routes_are_registered(self):
        list_match = resolve("/api/v1/core/notifications/")
        summary_match = resolve("/api/v1/core/notifications/bilan_livraison/")
        read_match = resolve("/api/v1/core/notifications/1/marquer_lue/")
        read_all_match = resolve("/api/v1/core/notifications/tout_marquer_lu/")

        self.assertEqual(list_match.url_name, "notifications-list")
        self.assertEqual(summary_match.url_name, "notifications-bilan-livraison")
        self.assertEqual(read_match.url_name, "notifications-marquer-lue")
        self.assertEqual(read_all_match.url_name, "notifications-tout-marquer-lu")
