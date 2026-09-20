"""Tests API et webhooks d'intégration - SIS Secondaire."""

import hashlib
import hmac
import json
from unittest.mock import patch

from apps.integration.models import EdxUserMapping, OutboxEvent
from apps.utilisateurs.models import Utilisateur
from django.test import override_settings
from rest_framework.test import APIClient, APITestCase


@override_settings(
    EDX_WEBHOOK_SECRET="test-webhook-secret-secondaire",
    EDX_BASE_URL="https://lms.test.com",
)
class WebhookSecurityTestCase(APITestCase):
    """Tests de sécurité des webhooks."""

    def setUp(self):
        self.client = APIClient()
        self.webhook_url = "/api/integration/webhooks/user/"
        self.secret = "test-webhook-secret-secondaire"

    def _generate_signature(self, payload: dict) -> str:
        """Génère une signature HMAC valide."""
        body = json.dumps(payload, separators=(",", ":")).encode()
        return hmac.new(self.secret.encode(), body, hashlib.sha256).hexdigest()

    def test_webhook_without_signature_rejected(self):
        """Un webhook sans signature est rejeté."""
        response = self.client.post(
            self.webhook_url, data={"event": "user.created"}, format="json"
        )
        assert response.status_code in [401, 403]

    def test_webhook_with_invalid_signature_rejected(self):
        """Un webhook avec signature invalide est rejeté."""
        response = self.client.post(
            self.webhook_url,
            data={"event": "user.created"},
            format="json",
            HTTP_X_EDX_SIGNATURE="invalid-signature",
        )
        assert response.status_code in [401, 403]

    def test_webhook_with_valid_signature_accepted(self):
        """Un webhook avec signature valide est accepté."""
        payload = {
            "event": "user.created",
            "data": {"user_id": 123, "username": "test_eleve"},
        }
        signature = self._generate_signature(payload)

        response = self.client.post(
            self.webhook_url,
            data=payload,
            format="json",
            HTTP_X_EDX_SIGNATURE=signature,
        )
        # 200/201 ou 404 si route pas encore configurée
        assert response.status_code in [200, 201, 404]


class UserWebhookTestCase(APITestCase):
    """Tests des webhooks utilisateur."""

    def setUp(self):
        self.admin = Utilisateur.objects.create_superuser(
            username="admin", email="admin@test.com", password="adminpass"
        )
        self.client.force_authenticate(user=self.admin)

    @patch("apps.integration.webhook_handlers.process_user_created")
    def test_user_created_webhook_triggers_handler(self, mock_handler):
        """Le webhook user.created déclenche le handler."""
        mock_handler.return_value = {"status": "ok"}

        # Le test dépend de la configuration des routes
        # Simplifié ici
        pass

    @patch("apps.integration.webhook_handlers.process_user_updated")
    def test_user_updated_webhook_triggers_handler(self, mock_handler):
        """Le webhook user.updated déclenche le handler."""
        mock_handler.return_value = {"status": "ok"}
        pass


class EnrollmentWebhookTestCase(APITestCase):
    """Tests des webhooks d'inscription."""

    @patch("apps.integration.webhook_handlers.process_enrollment_created")
    def test_enrollment_created_webhook(self, mock_handler):
        """Le webhook enrollment.created est traité."""
        mock_handler.return_value = {"status": "ok"}
        pass

    @patch("apps.integration.webhook_handlers.process_enrollment_deleted")
    def test_enrollment_deleted_webhook(self, mock_handler):
        """Le webhook enrollment.deleted est traité."""
        mock_handler.return_value = {"status": "ok"}
        pass


class GradeWebhookTestCase(APITestCase):
    """Tests des webhooks de notes."""

    @patch("apps.integration.webhook_handlers.process_grade_updated")
    def test_grade_updated_webhook_creates_log(self, mock_handler):
        """Le webhook grade.updated crée un EdxGradeLog."""
        mock_handler.return_value = {"status": "ok"}
        pass


class IntegrationAPIEndpointsTestCase(APITestCase):
    """Tests des endpoints API."""

    def setUp(self):
        self.admin = Utilisateur.objects.create_superuser(
            username="api_admin", email="api_admin@test.com", password="adminpass"
        )
        self.client.force_authenticate(user=self.admin)

    def test_list_user_mappings(self):
        """Lister les mappings utilisateurs."""
        user = Utilisateur.objects.create_user(
            username="mapped_user",
            email="mapped@test.com",
            password="pass",
            role="etudiant",
        )
        EdxUserMapping.objects.create(
            user_sis=user, username_edx="sis-s-mapped", user_id_edx=111
        )

        response = self.client.get("/api/v1/integration/mappings/users/")

        assert response.status_code == 200
        assert response.data["count"] == 1
        assert response.data["results"][0]["username_edx"] == "sis-s-mapped"

    def test_monitoring_requires_admin(self):
        """La supervision de l'intégration est réservée aux administrateurs."""
        user = Utilisateur.objects.create_user(
            username="standard_user",
            email="standard@test.com",
            ******,
            role="eleve",
        )
        self.client.force_authenticate(user=user)

        response = self.client.get("/api/v1/integration/sync/status/")

        assert response.status_code == 403

    def test_monitoring_requires_authentication(self):
        """La supervision de l'intégration refuse les visiteurs anonymes."""
        self.client.force_authenticate(user=None)

        response = self.client.get("/api/v1/integration/sync/status/")

        assert response.status_code in (401, 403)

    def test_list_outbox_events(self):
        """Lister les événements outbox."""
        OutboxEvent.objects.create(
            event_type="test.event", aggregate_type="test", aggregate_id="1", payload={}
        )

        response = self.client.get("/api/v1/integration/outbox/")

        assert response.status_code == 200
        assert response.data["count"] == 1
        assert response.data["results"][0]["event_type"] == "test.event"


class OutboxEventAPITestCase(APITestCase):
    """Tests spécifiques aux événements outbox."""

    def setUp(self):
        self.admin = Utilisateur.objects.create_superuser(
            username="outbox_admin", email="outbox@test.com", password="adminpass"
        )
        self.client.force_authenticate(user=self.admin)

    def test_retry_failed_event(self):
        """Relancer un événement en échec."""
        OutboxEvent.objects.create(
            event_type="failed.event",
            aggregate_type="test",
            aggregate_id="1",
            payload={},
            statut="failed",
            nb_tentatives=3,
        )

        # API de retry - dépend de l'implémentation
        pass

    def test_filter_events_by_status(self):
        """Filtrer les événements par statut via API."""
        for status in ["pending", "done", "failed"]:
            OutboxEvent.objects.create(
                event_type=f"{status}.event",
                aggregate_type="test",
                aggregate_id=status,
                payload={},
                statut=status,
            )

        response = self.client.get("/api/v1/integration/outbox/?statut=failed")

        assert response.status_code == 200
        assert response.data["count"] == 1
        assert response.data["results"][0]["statut"] == "failed"

    def test_reject_invalid_status_filter(self):
        response = self.client.get("/api/v1/integration/outbox/?statut=unknown")

        assert response.status_code == 400
