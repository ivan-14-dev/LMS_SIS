from unittest.mock import create_autospec, patch

import pytest
from apps.integration.edx_client import EdxClient
from apps.integration.models import EdxUserMapping
from apps.integration.sync_service import SyncService
from apps.integration.tests.tenant_test_case import TenantTestCase
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from rest_framework.exceptions import AuthenticationFailed

from sis_common.authentication import EdxJWTAuthentication


class LMSIdentityTests(TenantTestCase):
    previous = [("utilisateurs", "0004_alter_utilisateur_mfa_secret")]
    current = [("utilisateurs", "0005_utilisateur_integration_id")]

    @patch("apps.integration.sync_service.get_edx_client")
    def test_sync_rechecks_disabled_user_instead_of_using_a_stale_object(self, get_client):
        user = get_user_model().objects.create_user("disabled-provisioning", etablissement=self.tenant)
        get_user_model().objects.filter(pk=user.pk).update(is_active=False)
        with pytest.raises(ValueError, match="désactivé"):
            SyncService().sync_user_to_lms(user)
        get_client.return_value.create_user.assert_not_called()
        assert not EdxUserMapping.objects.filter(user_sis=user).exists()

    @patch("apps.integration.sync_service.get_edx_client")
    def test_sync_does_not_reactivate_revoked_mapping(self, get_client):
        user = get_user_model().objects.create_user("revoked-provisioning", etablissement=self.tenant)
        mapping = EdxUserMapping.objects.create(
            user_sis=user, username_edx="revoked-provisioning", user_id_edx=101, actif=False
        )
        with pytest.raises(ValueError, match="révoquée"):
            SyncService().sync_user_to_lms(user)
        get_client.return_value.create_user.assert_not_called()
        get_client.return_value.update_user.assert_not_called()
        mapping.refresh_from_db()
        assert not mapping.actif

    def test_lms_identity_cannot_bypass_local_mfa(self):
        user = get_user_model().objects.create_user(
            "federated-mfa",
            email="federated-mfa@example.test",
            etablissement=self.tenant,
            mfa_active=True,
            mfa_secret="JBSWY3DPEHPK3PXP",
        )
        EdxUserMapping.objects.create(user_sis=user, username_edx="federated-mfa", user_id_edx=101)
        with pytest.raises(AuthenticationFailed, match="connexion locale"):
            EdxJWTAuthentication._get_user({"preferred_username": "federated-mfa", "user_id": 101})
        user.refresh_from_db()
        assert user.mfa_active and user.mfa_secret == "JBSWY3DPEHPK3PXP"

    def test_upgrade_assigns_distinct_identifiers_without_changing_accounts(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.previous)
        try:
            old_user = executor.loader.project_state(self.previous).apps.get_model("utilisateurs", "Utilisateur")
            password = make_password("synthetic-migration-test")
            first = old_user.objects.create(
                username="before-identity-a",
                password=password,
                mfa_active=True,
                mfa_secret="synthetic-mfa-migration-value",
            )
            second = old_user.objects.create(username="before-identity-b", password=password)
        finally:
            # TestCase keeps inserts uncommitted; complete deferred FK checks before DDL.
            connection.check_constraints()
            MigrationExecutor(connection).migrate(self.current)

        user_model = get_user_model()
        first = user_model.objects.get(pk=first.pk)
        second = user_model.objects.get(pk=second.pk)
        assert first.integration_id != second.integration_id
        assert first.username == "before-identity-a"
        assert first.password == second.password == password
        assert first.mfa_active
        assert first.mfa_secret == "synthetic-mfa-migration-value"
        identifiers = list(user_model.objects.order_by("pk").values_list("integration_id", flat=True))
        MigrationExecutor(connection).migrate(self.current)
        assert list(user_model.objects.order_by("pk").values_list("integration_id", flat=True)) == identifiers

    def test_older_application_can_still_create_accounts_after_schema_upgrade(self):
        old_user = (
            MigrationExecutor(connection)
            .loader.project_state(self.previous)
            .apps.get_model("utilisateurs", "Utilisateur")
        )
        first = old_user.objects.create(username="old-code-a")
        second = old_user.objects.create(username="old-code-b")
        user_model = get_user_model()
        first = user_model.objects.get(pk=first.pk)
        second = user_model.objects.get(pk=second.pk)
        assert first.integration_id is not None
        assert first.integration_id != second.integration_id

    @patch("apps.integration.sync_service.get_edx_client")
    def test_reused_local_primary_key_does_not_reuse_lms_identity(self, get_client):
        client = create_autospec(EdxClient, instance=True)
        client.create_user.side_effect = [{"id": 101}, {"id": 102}]
        get_client.return_value = client
        user_model = get_user_model()
        first = user_model.objects.create_user("first-person", email="first@example.test", etablissement=self.tenant)
        identifier = first.pk
        first_mapping = SyncService().sync_user_to_lms(first)
        first_username = first_mapping.username_edx
        first.delete()
        second = user_model.objects.create_user(
            "second-person", pk=identifier, email="second@example.test", etablissement=self.tenant
        )
        second_mapping = SyncService().sync_user_to_lms(second)
        assert second_mapping.username_edx != first_username
        assert len(second_mapping.username_edx) <= 30

    @patch("apps.integration.sync_service.get_edx_client")
    def test_failed_provisioning_and_profile_change_keep_the_same_external_identity(self, get_client):
        client = create_autospec(EdxClient, instance=True)
        client.create_user.side_effect = [RuntimeError("network timeout"), {"id": 103}]
        get_client.return_value = client
        user = get_user_model().objects.create_user(
            "retry-person", email="before@example.test", etablissement=self.tenant
        )
        with pytest.raises(RuntimeError, match="network timeout"):
            SyncService().sync_user_to_lms(user)
        first_username = client.create_user.call_args.kwargs["username"]
        assert not EdxUserMapping.objects.filter(user_sis=user).exists()
        user.email = "after@example.test"
        user.save(update_fields=["email"])
        mapping = SyncService().sync_user_to_lms(user)
        assert mapping.username_edx == first_username
        assert client.create_user.call_args.kwargs["email"] == user.email
