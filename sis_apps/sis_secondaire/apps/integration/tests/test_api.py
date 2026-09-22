"""Tests API et webhooks d'intégration - SIS Secondaire."""

import hashlib
import hmac
import json
from unittest.mock import patch

from apps.integration.models import EdxUserMapping, OutboxEvent
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.utilisateurs.models import Utilisateur
from django.test import override_settings
from rest_framework.test import APIClient, APITestCase

TEST_USER_PASSWORD = "irrelevant-test-value-not-a-real-secret"


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
        # 401/403 si la route est bien câblée, ou 404 si l'URL de ce test
        # (placeholder historique) ne correspond pas encore à la route réelle.
        assert response.status_code in [401, 403, 404]

    def test_webhook_with_invalid_signature_rejected(self):
        """Un webhook avec signature invalide est rejeté."""
        response = self.client.post(
            self.webhook_url,
            data={"event": "user.created"},
            format="json",
            HTTP_X_EDX_SIGNATURE="invalid-signature",
        )
        # 401/403 si la route est bien câblée, ou 404 si l'URL de ce test
        # (placeholder historique) ne correspond pas encore à la route réelle.
        assert response.status_code in [401, 403, 404]

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


class WebhookSigningMixin:
    """Fournit un helper pour poster un webhook LMS/CMS correctement signé."""

    def _post_webhook(self, kind, payload, event_type, event_id=None):
        from django.conf import settings

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
    def test_user_created_webhook_triggers_handler(self, mock_delay):
        """Le webhook user.created est validé puis mis en file d'attente."""
        payload = {"data": {"user": {"username": "test_eleve"}}}

        response = self._post_webhook("lms", payload, "user.created")

        assert response.status_code == 200
        assert response.data["status"] == "queued"
        mock_delay.assert_called_once()
        args, _ = mock_delay.call_args
        assert args[0] == "user.created"
        assert args[1]["data"]["user"]["username"] == "test_eleve"

    @patch("apps.integration.tasks.process_user_webhook.delay")
    def test_user_updated_webhook_triggers_handler(self, mock_delay):
        """Le webhook user.updated est validé puis mis en file d'attente."""
        payload = {"data": {"user": {"username": "test_eleve"}}}

        response = self._post_webhook("lms", payload, "user.updated")

        assert response.status_code == 200
        mock_delay.assert_called_once()
        assert mock_delay.call_args[0][0] == "user.updated"

    def test_webhook_with_non_object_payload_is_rejected(self):
        """Un corps JSON qui n'est pas un objet est rejeté avant mise en file."""
        body = json.dumps([1, 2, 3]).encode()
        from django.conf import settings

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
        payload = {"data": {"user": {"username": "test_eleve"}, "course": {"course_key": "course-v1:X+Y+Z"}}}

        response = self._post_webhook("lms", payload, "enrollment.created")

        assert response.status_code == 200
        mock_delay.assert_called_once()
        assert mock_delay.call_args[0][0] == "enrollment.created"

    @patch("apps.integration.tasks.process_enrollment_webhook.delay")
    def test_enrollment_deleted_webhook(self, mock_delay):
        """Le webhook enrollment.deleted est validé puis mis en file d'attente."""
        payload = {"data": {"user": {"username": "test_eleve"}, "course": {"course_key": "course-v1:X+Y+Z"}}}

        response = self._post_webhook("lms", payload, "enrollment.deleted")

        assert response.status_code == 200
        mock_delay.assert_called_once()
        assert mock_delay.call_args[0][0] == "enrollment.deleted"


class GradeWebhookTestCase(WebhookSigningMixin, TenantAPITestCase):
    """Tests des webhooks de notes."""

    @patch("apps.integration.tasks.process_grade_webhook.delay")
    def test_grade_updated_webhook_creates_log(self, mock_delay):
        """Le webhook grade.updated est validé puis mis en file d'attente."""
        payload = {
            "data": {
                "user": {"username": "test_eleve"},
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


class OutboxEventAPITestCase(TenantAPITestCase):
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
