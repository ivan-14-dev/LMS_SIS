"""Tests API et Webhooks d'intégration LMS - SIS Supérieur."""

import hashlib
import hmac
import json
from unittest.mock import patch

from apps.integration.models import EdxUserMapping, OutboxEvent
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.utilisateurs.models import Utilisateur
from django.conf import settings
from django.test import override_settings

TEST_USER_PASSWORD = "irrelevant-test-value-not-a-real-secret"


class WebhookSecurityTestCase(TenantAPITestCase):
    """Tests de sécurité des webhooks."""

    def setUp(self):
        self.webhook_secret = "test-webhook-secret-123"

    def _sign_payload(self, payload: dict, secret: str) -> str:
        """Générer une signature HMAC pour le payload."""
        body = json.dumps(payload, separators=(",", ":")).encode()
        return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    @override_settings(WEBHOOK_SECRET="test-webhook-secret-123")
    def test_webhook_without_signature_rejected(self):
        """Webhook sans signature doit être rejeté."""
        response = self.client.post(
            "/api/v1/integration/webhook/lms/",
            data={"data": {}},
            format="json",
        )

        assert response.status_code == 401

    @override_settings(WEBHOOK_SECRET="test-webhook-secret-123")
    def test_webhook_with_invalid_signature_rejected(self):
        """Webhook avec signature invalide doit être rejeté."""
        response = self.client.post(
            "/api/v1/integration/webhook/lms/",
            data={"data": {}},
            format="json",
            HTTP_X_SIGNATURE="invalid-signature",
        )

        assert response.status_code == 401

    @override_settings(WEBHOOK_SECRET="test-webhook-secret-123")
    @patch("apps.integration.tasks.process_user_webhook.delay")
    def test_webhook_with_valid_signature_accepted(self, mock_delay):
        """Webhook avec signature valide doit être accepté."""
        payload = {"data": {"user": {"username": "test_etudiant"}}}
        signature = self._sign_payload(payload, self.webhook_secret)

        response = self.client.post(
            "/api/v1/integration/webhook/lms/",
            data=payload,
            format="json",
            HTTP_X_SIGNATURE=signature,
            HTTP_X_EVENT_TYPE="user.created",
        )

        assert response.status_code == 200
        assert response.data["status"] == "queued"
        mock_delay.assert_called_once()


class WebhookSigningMixin:
    """Fournit un helper pour poster un webhook LMS/CMS correctement signé."""

    def _post_webhook(self, kind, payload, event_type, event_id=None):
        url = f"/api/v1/integration/webhook/{kind}/"
        body = json.dumps(payload).encode()
        signature = hmac.new(
            settings.WEBHOOK_SECRET.encode(), body, hashlib.sha256
        ).hexdigest()
        headers = {
            "HTTP_X_SIGNATURE": signature,
            "HTTP_X_EVENT_TYPE": event_type,
        }
        if event_id:
            headers["HTTP_X_EVENT_ID"] = event_id
        return self.client.post(
            url, data=body, content_type="application/json", **headers
        )


class UserWebhookTestCase(WebhookSigningMixin, TenantAPITestCase):
    """Tests des webhooks utilisateur."""

    def setUp(self):
        self.admin = Utilisateur.objects.create_superuser(
            "admin", "admin@test.com", TEST_USER_PASSWORD
        )
        self.client.force_authenticate(user=self.admin)

    @patch("apps.integration.tasks.process_user_webhook.delay")
    def test_user_created_webhook(self, mock_delay):
        """Le webhook user.created est validé puis mis en file d'attente."""
        payload = {
            "data": {
                "user": {
                    "id": 12345,
                    "username": "new_lms_user",
                    "email": "new@example.com",
                    "name": "New User",
                }
            }
        }

        response = self._post_webhook("lms", payload, "user.created")

        assert response.status_code == 200
        assert response.data["status"] == "queued"
        mock_delay.assert_called_once()
        args, _ = mock_delay.call_args
        assert args[0] == "user.created"
        assert args[1]["data"]["user"]["username"] == "new_lms_user"

    def test_webhook_with_non_object_payload_is_rejected(self):
        """Un corps JSON qui n'est pas un objet est rejeté avant mise en file."""
        body = json.dumps([1, 2, 3]).encode()
        signature = hmac.new(
            settings.WEBHOOK_SECRET.encode(), body, hashlib.sha256
        ).hexdigest()

        response = self.client.post(
            "/api/v1/integration/webhook/lms/",
            data=body,
            content_type="application/json",
            HTTP_X_SIGNATURE=signature,
            HTTP_X_EVENT_TYPE="user.created",
        )

        assert response.status_code == 400
        assert "error" in response.data

    def test_webhook_with_non_object_data_field_is_rejected(self):
        """Un champ ``data`` qui n'est pas un objet est rejeté avant mise en file."""
        response = self._post_webhook("lms", {"data": "not-an-object"}, "user.created")

        assert response.status_code == 400
        assert "error" in response.data


class EnrollmentWebhookTestCase(WebhookSigningMixin, TenantAPITestCase):
    """Tests des webhooks d'inscription."""

    @patch("apps.integration.tasks.process_enrollment_webhook.delay")
    def test_enrollment_created_webhook(self, mock_delay):
        """Le webhook enrollment.created est validé puis mis en file d'attente."""
        payload = {
            "data": {
                "user": {"username": "test_etudiant"},
                "course": {"course_key": "course-v1:X+Y+Z"},
            }
        }

        response = self._post_webhook("lms", payload, "enrollment.created")

        assert response.status_code == 200
        mock_delay.assert_called_once()
        assert mock_delay.call_args[0][0] == "enrollment.created"


class GradeWebhookTestCase(WebhookSigningMixin, TenantAPITestCase):
    """Tests des webhooks de notes."""

    @patch("apps.integration.tasks.process_grade_webhook.delay")
    def test_grade_updated_webhook(self, mock_delay):
        """Le webhook grade.updated est validé puis mis en file d'attente."""
        payload = {
            "data": {
                "user": {"username": "test_etudiant"},
                "course": {"course_key": "course-v1:X+Y+Z"},
                "subsection_id": "block-v1:sub1",
                "score": 15,
                "max_score": 20,
            }
        }

        response = self._post_webhook("lms", payload, "grade.updated")

        assert response.status_code == 200
        mock_delay.assert_called_once()
        assert mock_delay.call_args[0][0] == "grade.updated"


class IntegrationAPIEndpointsTestCase(TenantAPITestCase):
    """Tests des endpoints API d'intégration."""

    def setUp(self):
        self.admin_user = Utilisateur.objects.create_superuser(
            "api_admin", "admin@test.com", TEST_USER_PASSWORD
        )
        self.client.force_authenticate(user=self.admin_user)

    def test_list_user_mappings_authenticated(self):
        """Un administrateur peut lister les mappings utilisateurs."""
        # Créer quelques mappings
        user1 = Utilisateur.objects.create_user(
            "mapped1", "m1@test.com", TEST_USER_PASSWORD
        )
        user2 = Utilisateur.objects.create_user(
            "mapped2", "m2@test.com", TEST_USER_PASSWORD
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
            "standard_user", "standard@test.com", TEST_USER_PASSWORD
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


class SyncServiceAPITestCase(TenantAPITestCase):
    """Tests des endpoints de synchronisation manuelle."""

    def setUp(self):
        self.admin_user = Utilisateur.objects.create_superuser(
            "sync_admin", "syncadmin@test.com", TEST_USER_PASSWORD
        )
        self.client.force_authenticate(user=self.admin_user)

    @patch("apps.integration.api.SyncService")
    def test_trigger_user_sync(self, mock_service_class):
        """Déclencher une synchronisation utilisateur manuelle."""
        user = Utilisateur.objects.create_user(
            "sync_target", "target@test.com", TEST_USER_PASSWORD
        )
        mock_service = mock_service_class.return_value
        mock_mapping = mock_service.sync_user_to_lms.return_value
        mock_mapping.username_edx = "sis-u-sync-target"
        mock_mapping.user_id_edx = 42

        response = self.client.post(f"/api/v1/integration/sync/user/{user.id}/")

        assert response.status_code == 200
        assert response.data["status"] == "ok"
        assert response.data["username_edx"] == "sis-u-sync-target"
        mock_service.sync_user_to_lms.assert_called_once()

    def test_trigger_user_sync_unknown_user_returns_404(self):
        """Synchroniser un utilisateur inexistant renvoie 404."""
        response = self.client.post("/api/v1/integration/sync/user/999999/")

        assert response.status_code == 404


class HealthCheckTestCase(TenantAPITestCase):
    """Tests du health check intégration."""

    def setUp(self):
        self.admin_user = Utilisateur.objects.create_superuser(
            "health_admin", "health_admin@test.com", TEST_USER_PASSWORD
        )
        self.client.force_authenticate(user=self.admin_user)

    @patch("apps.integration.api.get_edx_client")
    def test_integration_health_check(self, mock_get_client):
        """Vérifier le statut de connexion LMS/CMS."""
        mock_client = mock_get_client.return_value
        mock_client.health_check.return_value = {"lms": True, "cms": True}

        response = self.client.get("/api/v1/integration/health/")

        assert response.status_code == 200
        assert response.data["connected"] is True
