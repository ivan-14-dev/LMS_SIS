import json
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
import requests
from apps.integration import api
from apps.integration.models import EdxAccessIntent, OutboxEvent
from apps.integration.tasks import publish_tenant_outbox_events
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from apps.integration.tests.test_sync_service import EnrollmentFixtureMixin
from django.contrib.auth import get_user_model
from django.db import connection
from django.utils import timezone
from django_tenants.utils import schema_context
from rest_framework.pagination import PageNumberPagination
from rest_framework.test import APIRequestFactory, force_authenticate

from sis_common.lms_access_sync import queue_access

BASE = "/api/v1/integration/outbox/"


class LMSOutboxAPITests(TenantAPITestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user(
            username="outbox-admin", is_staff=True, etablissement=self.tenant
        )
        self.client.force_authenticate(self.admin)
        self.dispatch = self.enterContext(patch("apps.integration.tasks.publish_tenant_outbox_events.delay"))
        self.dispatch.return_value = SimpleNamespace(id="synthetic-task-id")

    def test_administrator_queues_only_current_tenant_without_editing_evidence(self):
        event = OutboxEvent.objects.create(
            event_type="access.set", aggregate_type="access", aggregate_id="12",
            payload={"requested_at": timezone.now().isoformat()}, statut="pending", erreur="Lost response",
        )
        before = OutboxEvent.objects.values().get(pk=event.pk)
        response = self.client.post(f"{BASE}process/", {}, format="json")
        assert response.status_code == 202
        assert response.data == {"status": "queued", "task_id": "synthetic-task-id"}
        self.dispatch.assert_called_once_with(self.tenant.pk, self.tenant.schema_name)
        assert OutboxEvent.objects.values().get(pk=event.pk) == before

    def test_lower_roles_and_anonymous_users_cannot_dispatch_or_read_evidence(self):
        for user in (
            get_user_model().objects.create_user(username="outbox-teacher", role="enseignant"),
            get_user_model().objects.create_user(username="outbox-student"),
            None,
        ):
            with self.subTest(user=user):
                self.client.force_authenticate(user)
                assert self.client.post(f"{BASE}process/", {}, format="json").status_code in (401, 403)
                assert self.client.get(BASE).status_code in (401, 403)
        self.dispatch.assert_not_called()

    def test_invalid_payloads_and_scope_overrides_never_dispatch(self):
        for payload in ([], ["all"], "all", None, {"tenant_id": self.tenant.pk},
                        {"schema_name": "public"}, {"event_id": 1}, {"confirm": True}, {"statut": "dead"}):
            with self.subTest(payload=payload):
                # Explicit JSON also tests null and scalar payloads, not the client's empty-body fallback.
                response = self.client.post(f"{BASE}process/", json.dumps(payload), content_type="application/json")
                assert response.status_code == 400
        assert self.client.post(f"{BASE}process/?schema_name=other", {}, format="json").status_code == 400
        assert self.client.post(f"{BASE}process/", {"event_id": 1}, format="multipart").status_code == 415
        assert self.client.get(f"{BASE}process/").status_code == 405
        self.dispatch.assert_not_called()

    def test_missing_public_or_mismatched_tenant_is_rejected_before_any_dispatch_or_query(self):
        factory = APIRequestFactory()
        for tenant in (
            None,
            SimpleNamespace(pk=self.tenant.pk, schema_name="public"),
            SimpleNamespace(pk=self.tenant.pk, schema_name="other"),
            SimpleNamespace(pk=self.tenant.pk + 100, schema_name=self.tenant.schema_name),
        ):
            with self.subTest(tenant=tenant):
                request = factory.post(f"{BASE}process/", {}, format="json")
                request.tenant = tenant
                force_authenticate(request, self.admin)
                assert api.process_outbox(request).status_code == 403
                request = factory.get(BASE)
                request.tenant = tenant
                force_authenticate(request, self.admin)
                assert api.outbox_events(request).status_code == 403
        with schema_context("public"):
            request = factory.post(f"{BASE}process/", {}, format="json")
            request.tenant = self.tenant
            force_authenticate(request, self.admin)
            assert api.process_outbox(request).status_code == 403
        self.dispatch.assert_not_called()

    def test_broker_failure_is_logged_as_unconfirmed_and_preserves_events(self):
        event = OutboxEvent.objects.create(
            event_type="access.set", aggregate_type="access", aggregate_id="12",
            payload={"requested_at": timezone.now().isoformat()}, statut="dead", erreur="Permanent conflict",
        )
        before = OutboxEvent.objects.values().get(pk=event.pk)
        self.dispatch.side_effect = ConnectionError("broker unavailable")
        with self.assertLogs("sis_common.lms_outbox", level="ERROR") as logs:
            response = self.client.post(f"{BASE}process/", {}, format="json")
        assert response.status_code == 503
        assert "pas confirmée" in response.data["error"]
        assert f"tenant_id={self.tenant.pk}" in logs.output[0]
        assert OutboxEvent.objects.values().get(pk=event.pk) == before

    def test_failure_filter_is_paginated_and_never_hides_pending_in_the_unfiltered_view(self):
        events = [
            OutboxEvent.objects.create(
                event_type="access.set", aggregate_type="access", aggregate_id=str(index), payload={},
                statut=value, erreur="Retained evidence",
            )
            for index, value in enumerate(("pending", "done", "dead", "failed", "dead"))
        ]
        with patch.object(PageNumberPagination, "page_size", 2):
            first = self.client.get(f"{BASE}?statut=failed&statut=dead")
            assert first.status_code == 200
            assert first.data["count"] == 3
            assert "statut=failed" in first.data["next"]
            assert "statut=dead" in first.data["next"]
            second = self.client.get(f"{BASE}?statut=failed&statut=dead&page=2")
            rows = first.data["results"] + second.data["results"]
            assert {row["id"] for row in rows} == {event.pk for event in events[2:]}
            assert all(row["erreur"] == "Retained evidence" for row in rows)
        assert self.client.get(BASE).data["count"] == 5
        assert self.client.get(f"{BASE}?statut=pending").data["results"][0]["id"] == events[0].pk
        for query in ("statut=invalid", "statut=dead&statut=invalid", "statut="):
            assert self.client.get(f"{BASE}?{query}").status_code == 400
        assert OutboxEvent.objects.count() == 5
        self.dispatch.assert_not_called()

    def test_worker_uses_one_registered_schema_and_restores_context_without_enumerating_tenants(self):
        visited = []
        with patch("apps.integration.tasks._iter_tenant_schemas") as all_tenants, patch(
            "apps.integration.tasks._publish_outbox_events_for_current_schema",
            side_effect=lambda: visited.append(connection.schema_name) or 7,
        ) as publisher, schema_context("public"):
            assert publish_tenant_outbox_events(self.tenant.pk, self.tenant.schema_name) == 7
            assert connection.schema_name == "public"
            assert visited == [self.tenant.schema_name]
            publisher.assert_called_once_with()
            all_tenants.assert_not_called()
            for tenant_id, schema in ((self.tenant.pk, "public"), (self.tenant.pk, "other"),
                                      (self.tenant.pk + 100, self.tenant.schema_name), (None, None)):
                with self.subTest(tenant_id=tenant_id, schema=schema), pytest.raises(ValueError, match="invalide"):
                    publish_tenant_outbox_events(tenant_id, schema)
            publisher.assert_called_once_with()


class LMSOutboxReplayTests(EnrollmentFixtureMixin, TenantAPITestCase):
    def test_tenant_task_preserves_withdrawal_versions_backoff_and_permanent_evidence(self):
        remote = Mock()
        self.enterContext(patch("apps.integration.sync_service.get_edx_client", return_value=remote))
        intent, pending = queue_access(self.user, self.course_mapping, kind="enrollment", active=False)
        requested_at = intent.requested_at
        pending.nb_tentatives = 6
        pending.derniere_tentative = timezone.now()
        pending.save()
        dead = OutboxEvent.objects.create(
            event_type="access.set", aggregate_type="access", aggregate_id=str(intent.pk),
            payload={"requested_at": requested_at.isoformat()}, statut="dead", erreur="Permanent conflict",
        )
        evidence = OutboxEvent.objects.values().get(pk=dead.pk)
        assert publish_tenant_outbox_events(self.tenant.pk, self.tenant.schema_name) == 0
        remote.set_course_access.assert_not_called()
        OutboxEvent.objects.filter(pk=pending.pk).update(derniere_tentative=timezone.now() - timedelta(minutes=6))
        remote.set_course_access.side_effect = requests.ConnectionError("LMS unavailable")
        assert publish_tenant_outbox_events(self.tenant.pk, self.tenant.schema_name) == 1
        pending.refresh_from_db()
        assert pending.statut == "pending"
        assert pending.nb_tentatives == 7
        assert remote.set_course_access.call_args.kwargs["requested_at"] == requested_at
        assert not remote.set_course_access.call_args.kwargs["active"]
        assert EdxAccessIntent.objects.get(pk=intent.pk).requested_at == requested_at
        assert OutboxEvent.objects.values().get(pk=dead.pk) == evidence
