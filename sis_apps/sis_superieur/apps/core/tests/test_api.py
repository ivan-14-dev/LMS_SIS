"""API tests for core."""

from apps.integration.tests.tenant_test_case import TenantAPITestCase
from django.test import SimpleTestCase
from django.urls import resolve


class MetricsEndpointTestCase(TenantAPITestCase):
    """L'endpoint ``/metrics/`` doit exposer un format Prometheus valide."""

    def test_metrics_returns_prometheus_exposition_format(self):
        response = self.client.get("/metrics/")

        assert response.status_code == 200
        assert response["Content-Type"].startswith("text/plain")

        body = response.content.decode("utf-8")
        assert "# HELP sis_users_total" in body
        assert "# TYPE sis_users_total gauge" in body
        assert "sis_users_total " in body
        assert "sis_outbox_events_dead " in body
        assert "sis_metrics_scrape_timestamp_seconds " in body


class CoreAPITestCase(SimpleTestCase):
    def test_workflow_event_routes_are_registered(self):
        list_match = resolve("/api/v1/core/workflow-events/")
        summary_match = resolve("/api/v1/core/workflow-events/bilan/")
        export_match = resolve("/api/v1/core/workflow-events/exporter/")

        assert list_match.url_name == "workflow-event-list"
        assert summary_match.url_name == "workflow-event-bilan"
        assert export_match.url_name == "workflow-event-exporter"

    def test_notification_routes_are_registered(self):
        list_match = resolve("/api/v1/core/notifications/")
        summary_match = resolve("/api/v1/core/notifications/bilan_livraison/")
        trends_match = resolve("/api/v1/core/notifications/tendances_livraison/")
        read_match = resolve("/api/v1/core/notifications/1/marquer_lue/")
        read_all_match = resolve("/api/v1/core/notifications/tout_marquer_lu/")

        assert list_match.url_name == "notifications-list"
        assert summary_match.url_name == "notifications-bilan-livraison"
        assert trends_match.url_name == "notifications-tendances-livraison"
        assert read_match.url_name == "notifications-marquer-lue"
        assert read_all_match.url_name == "notifications-tout-marquer-lu"
