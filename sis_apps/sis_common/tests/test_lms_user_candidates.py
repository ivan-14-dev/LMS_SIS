from types import SimpleNamespace
from unittest.mock import patch

from apps.integration.api import sync_status
from apps.integration.models import EdxUserMapping, OutboxEvent
from apps.integration.tests.tenant_test_case import TenantAPITestCase
from django.contrib.auth import get_user_model
from django_tenants.utils import schema_context
from guardian.shortcuts import get_anonymous_user
from rest_framework.pagination import PageNumberPagination
from rest_framework.test import APIRequestFactory, force_authenticate

from sis_common.lms_identity import lms_username
from sis_common.lms_user_candidates import user_candidates

BASE = "/api/v1/integration/mappings/users/candidates/"


class LMSUserCandidateTests(TenantAPITestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user(
            username="candidate-admin", is_staff=True, etablissement=self.tenant
        )
        self.client.force_authenticate(self.admin)
        EdxUserMapping.objects.create(user_sis=self.admin, username_edx=lms_username(self.admin))

    def test_listing_is_paginated_read_only_and_excludes_all_existing_associations(self):
        user_model = get_user_model()
        users = [
            user_model.objects.create_user(
                username=f"candidate-{number}", first_name="Identity", last_name=str(number),
                etablissement=self.tenant,
            )
            for number in range(5)
        ]
        user_model.objects.filter(pk=users[4].pk).update(is_active=False)
        for user, active in ((users[2], True), (users[3], False)):
            EdxUserMapping.objects.create(user_sis=user, username_edx=lms_username(user), actif=active)
        legacy = user_model.objects.create_user(username="candidate-legacy")
        before_users = list(user_model.objects.order_by("pk").values())
        before_mappings = list(EdxUserMapping.objects.order_by("pk").values())
        with patch.object(PageNumberPagination, "page_size", 2), patch(
            "apps.integration.sync_service.get_edx_client"
        ) as client:
            first = self.client.get(BASE)
            assert first.status_code == 200
            assert first.data["count"] == 3
            assert first.data["next"].endswith("?page=2")
            second = self.client.get(f"{BASE}?page=2")
            assert second.status_code == 200
            assert second.data["next"] is None
            assert [row["user_sis"] for row in first.data["results"] + second.data["results"]] == [
                users[0].pk, users[1].pk, legacy.pk,
            ]
            assert first.data["results"][0] == {
                "user_sis": users[0].pk,
                "user_sis_username": users[0].username,
                "user_sis_name": "Identity 0",
                "username_edx": lms_username(users[0]),
                "user_id_edx": None,
                "actif": True,
            }
            assert second.data["results"][0]["user_sis_name"] == legacy.username
            client.assert_not_called()
        assert list(user_model.objects.order_by("pk").values()) == before_users
        assert list(EdxUserMapping.objects.order_by("pk").values()) == before_mappings
        assert not OutboxEvent.objects.exists()

    def test_association_removes_candidate_without_changing_its_canonical_identity(self):
        user = get_user_model().objects.create_user(username="first-association", etablissement=self.tenant)
        before = self.client.get(BASE).data["results"][0]
        with patch("apps.integration.sync_service.get_edx_client") as client:
            client.return_value.create_user.return_value = {"id": 101}
            response = self.client.post(f"/api/v1/integration/sync/user/{user.pk}/", {}, format="json")
        assert response.status_code == 200
        assert response.data["username_edx"] == before["username_edx"]
        assert response.data["user_id_edx"] == 101
        assert EdxUserMapping.objects.get(user_sis=user).username_edx == before["username_edx"]
        assert self.client.get(BASE).data["count"] == 0
        assert self.client.get(BASE).data["results"] == []

    def test_guardian_system_identity_is_not_a_human_candidate_even_when_active(self):
        anonymous = get_anonymous_user()
        get_user_model().objects.filter(pk=anonymous.pk).update(is_active=True)
        response = self.client.get(BASE)
        assert response.status_code == 200
        assert response.data["results"] == []

    def test_lower_roles_inactive_administrator_and_anonymous_are_denied(self):
        users = [
            get_user_model().objects.create_user(username="candidate-teacher", role="enseignant"),
            get_user_model().objects.create_user(username="candidate-student"),
            get_user_model().objects.create_user(username="candidate-disabled-admin", is_staff=True, is_active=False),
            None,
        ]
        for user in users:
            with self.subTest(user=user):
                self.client.force_authenticate(user)
                assert self.client.get(BASE).status_code in (401, 403)

    def test_public_missing_and_inconsistent_tenants_are_denied(self):
        factory = APIRequestFactory()
        for tenant in (
            None,
            SimpleNamespace(pk=self.tenant.pk, schema_name="public"),
            SimpleNamespace(pk=self.tenant.pk, schema_name="other"),
            SimpleNamespace(pk=self.tenant.pk + 100, schema_name=self.tenant.schema_name),
        ):
            with self.subTest(tenant=tenant):
                request = factory.get(BASE)
                request.tenant = tenant
                force_authenticate(request, self.admin)
                assert user_candidates(request).status_code == 403
                status_request = factory.get("/api/v1/integration/sync/status/")
                status_request.tenant = tenant
                force_authenticate(status_request, self.admin)
                assert sync_status(status_request).status_code == 403
        with schema_context("public"):
            request = factory.get(BASE)
            request.tenant = self.tenant
            force_authenticate(request, self.admin)
            assert user_candidates(request).status_code == 403
            status_request = factory.get("/api/v1/integration/sync/status/")
            status_request.tenant = self.tenant
            force_authenticate(status_request, self.admin)
            assert sync_status(status_request).status_code == 403

    def test_foreign_institution_accounts_are_not_exposed_or_allowed_to_list(self):
        foreign = type(self.tenant)(schema_name="candidate_foreign")
        self.setup_tenant(foreign)
        foreign.auto_create_schema = False
        with schema_context("public"):
            foreign.save()
        foreign_user = get_user_model().objects.create_user(
            username="foreign-candidate", etablissement=foreign, is_staff=True
        )
        response = self.client.get(BASE)
        assert response.status_code == 200
        assert response.data["results"] == []
        self.client.force_authenticate(foreign_user)
        assert self.client.get(BASE).status_code == 403

    def test_manual_sync_cannot_provision_an_account_from_another_institution(self):
        foreign = type(self.tenant)(schema_name="candidate_sync_foreign")
        self.setup_tenant(foreign)
        foreign.auto_create_schema = False
        with schema_context("public"):
            foreign.save()
        foreign_user = get_user_model().objects.create_user(username="foreign-sync-target", etablissement=foreign)
        with patch("apps.integration.sync_service.get_edx_client") as remote:
            remote.return_value.create_user.return_value = {"id": 101}
            response = self.client.post(f"/api/v1/integration/sync/user/{foreign_user.pk}/", {}, format="json")
        assert response.status_code == 404
        remote.assert_not_called()
        assert not EdxUserMapping.objects.filter(user_sis=foreign_user).exists()

    def test_manual_sync_rejects_an_administrator_from_another_institution(self):
        foreign = type(self.tenant)(schema_name="candidate_sync_actor")
        self.setup_tenant(foreign)
        foreign.auto_create_schema = False
        with schema_context("public"):
            foreign.save()
        foreign_admin = get_user_model().objects.create_user(
            username="foreign-sync-admin", etablissement=foreign, is_staff=True
        )
        local_user = get_user_model().objects.create_user(username="local-sync-target", etablissement=self.tenant)
        self.client.force_authenticate(foreign_admin)
        with patch("apps.integration.sync_service.get_edx_client") as remote:
            remote.return_value.create_user.return_value = {"id": 101}
            response = self.client.post(f"/api/v1/integration/sync/user/{local_user.pk}/", {}, format="json")
        assert response.status_code == 403
        assert self.client.post("/api/v1/integration/sync/course/", {}, format="json").status_code == 403
        remote.assert_not_called()
        assert not EdxUserMapping.objects.filter(user_sis=local_user).exists()

    def test_foreign_administrator_cannot_use_integration_admin_routes(self):
        foreign = type(self.tenant)(schema_name="candidate_admin_foreign")
        self.setup_tenant(foreign)
        foreign.auto_create_schema = False
        with schema_context("public"):
            foreign.save()
        foreign_admin = get_user_model().objects.create_user(
            username="foreign-integration-admin", etablissement=foreign, is_staff=True
        )
        self.client.force_authenticate(foreign_admin)
        reads = (
            "/api/v1/integration/sync/status/",
            "/api/v1/integration/mappings/users/",
            "/api/v1/integration/mappings/courses/",
            "/api/v1/integration/outbox/",
            "/api/v1/integration/health/",
            "/api/v1/integration/sync/course/999999/publication/",
        )
        writes = (
            "/api/v1/integration/outbox/process/",
            "/api/v1/integration/sync/user/999999/",
            "/api/v1/integration/sync/course/",
            "/api/v1/integration/sync/course-live/999999/",
            "/api/v1/integration/sync/grade/",
            "/api/v1/integration/sync/certificate/",
            "/api/v1/integration/sync/course/999999/publication/",
        )
        with patch("apps.integration.api.get_edx_client") as remote:
            remote.return_value.health_check.return_value = {"lms": True, "cms": True}
            for path in reads:
                with self.subTest(path=path):
                    assert self.client.get(path).status_code == 403
            for path in writes:
                with self.subTest(path=path):
                    assert self.client.post(path, {}, format="json").status_code == 403
            remote.assert_not_called()
        assert not OutboxEvent.objects.exists()

    def test_local_administrator_can_still_read_integration_state(self):
        assert self.client.get("/api/v1/integration/sync/status/").data["users_mapped"] == 1
        assert self.client.get("/api/v1/integration/mappings/users/").data["count"] == 1
        assert self.client.get("/api/v1/integration/mappings/courses/").data["count"] == 0

    def test_scope_overrides_invalid_pages_and_mutation_methods_are_rejected(self):
        for query in ("schema_name=other", "tenant_id=123", "role=admin", "page=1&page=2", "search=someone"):
            with self.subTest(query=query):
                assert self.client.get(f"{BASE}?{query}").status_code == 400
        assert self.client.get(f"{BASE}?page=invalid").status_code == 404
        assert self.client.post(BASE, {}, format="json").status_code == 405
