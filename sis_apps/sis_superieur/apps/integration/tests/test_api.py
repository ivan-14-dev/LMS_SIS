"""Tests API et Webhooks d'intégration LMS - SIS Supérieur."""

import hashlib
import hmac
import json
from unittest.mock import patch

from apps.integration.models import EdxUserMapping, OutboxEvent
from apps.utilisateurs.models import Utilisateur
from django.test import TestCase, override_settings
from rest_framework.test import APIClient, APITestCase


class WebhookSecurityTestCase(TestCase):
    """Tests de sécurité des webhooks."""

    def setUp(self):
        self.client = APIClient()
        self.webhook_secret = "test-webhook-secret-123"

    def _sign_payload(self, payload: dict, secret: str) -> str:
        """Générer une signature HMAC pour le payload."""
        body = json.dumps(payload, separators=(",", ":")).encode()
        return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    @override_settings(WEBHOOK_SECRET="test-webhook-secret-123")
    def test_webhook_without_signature_rejected(self):
        """Webhook sans signature doit être rejeté."""
        # Ce test dépend de l'implémentation du endpoint webhook
        # Placeholder pour quand l'endpoint sera implémenté
        pass

    @override_settings(WEBHOOK_SECRET="test-webhook-secret-123")
    def test_webhook_with_invalid_signature_rejected(self):
        """Webhook avec signature invalide doit être rejeté."""
        pass

    @override_settings(WEBHOOK_SECRET="test-webhook-secret-123")
    def test_webhook_with_valid_signature_accepted(self):
        """Webhook avec signature valide doit être accepté."""
        pass


class UserWebhookTestCase(APITestCase):
    """Tests des webhooks utilisateur."""

    def test_user_created_webhook(self):
        """Traitement du webhook user.created."""
        payload = {
            "event": "user.created",
            "user": {
                "id": 12345,
                "username": "new_lms_user",
                "email": "new@example.com",
                "name": "New User",
            },
            "timestamp": "2026-07-22T10:00:00Z",
        }
        # Test du handler directement
        from apps.etudiants.models import Etudiant
        from apps.integration.models import EdxCourseMapping, EdxEnrollment, EdxGradeLog, EdxUserMapping
        from apps.integration.webhook_handlers import WebhookHandler
        from apps.notes.models import Note

        handler = WebhookHandler(
            EdxUserMapping, EdxCourseMapping, EdxEnrollment, EdxGradeLog, Etudiant, Note
        )
        handler.handle_user_created(payload)

        # Vérifier que le mapping existe maintenant
        # (peut ne pas exister si l'utilisateur SIS n'existe pas encore)


class EnrollmentWebhookTestCase(APITestCase):
    """Tests des webhooks d'inscription."""

    def test_enrollment_created_webhook(self):
        """Traitement du webhook enrollment.created."""
        # Test placeholder


class GradeWebhookTestCase(APITestCase):
    """Tests des webhooks de notes."""

    def test_grade_updated_webhook(self):
        """Traitement du webhook grade.updated."""
        # Test placeholder


class IntegrationAPIEndpointsTestCase(APITestCase):
    """Tests des endpoints API d'intégration."""

    def setUp(self):
        self.admin_user = Utilisateur.objects.create_superuser(
            username="api_admin", email="admin@test.com", password="adminpass123"
        )
        self.client.force_authenticate(user=self.admin_user)

    def test_list_user_mappings_authenticated(self):
        """Un administrateur peut lister les mappings utilisateurs."""
        # Créer quelques mappings
        user1 = Utilisateur.objects.create_user(
            username="mapped1", email="m1@test.com", password="pass"
        )
        user2 = Utilisateur.objects.create_user(
            username="mapped2", email="m2@test.com", password="pass"
        )
        EdxUserMapping.objects.create(user_sis=user1, username_edx="edx1")
        EdxUserMapping.objects.create(user_sis=user2, username_edx="edx2")

        response = self.client.get("/api/v1/integration/mappings/users/")

        assert response.status_code == 200
        assert response.data["count"] == 2
        assert {item["username_edx"] for item in response.data["results"]} == {
            "edx1",
            "edx2",
        }

    def test_list_user_mappings_unauthenticated(self):
        """Accès non authentifié refusé."""
        self.client.force_authenticate(user=None)

        response = self.client.get("/api/v1/integration/mappings/users/")

        assert response.status_code in (401, 403)

    def test_list_user_mappings_requires_admin(self):
        """Un utilisateur standard ne peut pas consulter les mappings."""
        user = Utilisateur.objects.create_user(
            username="standard_user",
            email="standard@test.com",
        )
        self.client.force_authenticate(user=user)

        response = self.client.get("/api/v1/integration/mappings/users/")

        assert response.status_code == 403

    def test_outbox_events_list(self):
        """Lister les événements outbox."""
        OutboxEvent.objects.create(
            event_type="test.event",
            aggregate_type="test",
            aggregate_id="1",
            payload={"test": True},
        )

        response = self.client.get("/api/v1/integration/outbox/")

        assert response.status_code == 200
        assert response.data["count"] == 1
        assert response.data["results"][0]["event_type"] == "test.event"

    def test_sync_status_endpoint(self):
        """Endpoint de statut de synchronisation."""
        response = self.client.get("/api/v1/integration/sync/status/")

        assert response.status_code == 200
        assert response.data["users_mapped"] == 0
        assert response.data["courses_mapped"] == 0
        assert response.data["enrollments_active"] == 0


class SyncServiceAPITestCase(APITestCase):
    """Tests des endpoints de synchronisation manuelle."""

    def setUp(self):
        self.admin_user = Utilisateur.objects.create_superuser(
            username="sync_admin", email="syncadmin@test.com", password="adminpass123"
        )
        self.client.force_authenticate(user=self.admin_user)

    @patch("apps.integration.sync_service.SyncService")
    def test_trigger_user_sync(self, mock_service):
        """Déclencher une synchronisation utilisateur manuelle."""
        # Placeholder pour l'endpoint POST /api/v1/integration/sync/user/{id}/
        pass

    @patch("apps.integration.sync_service.SyncService")
    def test_trigger_full_reconciliation(self, mock_service):
        """Déclencher une réconciliation complète."""
        # Placeholder pour l'endpoint POST /api/v1/integration/reconcile/
        pass


class HealthCheckTestCase(APITestCase):
    """Tests du health check intégration."""

    @patch("apps.integration.edx_client.EdxClient.health_check")
    def test_integration_health_check(self, mock_health):
        """Vérifier le statut de connexion LMS/CMS."""
        mock_health.return_value = {"lms": True, "cms": True}
        # Placeholder pour GET /api/v1/integration/health/
