from io import StringIO
from unittest.mock import patch
from urllib.parse import urlsplit

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Permission
from django.contrib.auth.tokens import default_token_generator
from django.core.management import call_command
from django.test import RequestFactory, TestCase, override_settings
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.test import APIClient

from .authentication import ProvisioningAuthentication
from .models import ManagedAccount


@override_settings(ALLOWED_HOSTS=["testserver"], SECURE_SSL_REDIRECT=False)
class ProvisioningTests(TestCase):
    def setUp(self):
        self.manager = get_user_model().objects.create_user(
            "provisioning_test_service", email="provisioning-service@example.test"
        )
        self.manager.user_permissions.add(
            Permission.objects.get(content_type__app_label="sis_provisioning", codename="provision_accounts")
        )
        self.client = APIClient()
        self.client.force_authenticate(self.manager)
        self.url = "/api/sis/v1/accounts/sis_provisioning_test/"
        self.payload = {"email": "sis-provisioning@example.test", "name": "Synthetic Learner"}

    def provision(self):
        response = self.client.post(self.url, self.payload, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        return response.data

    def test_creation_and_retry_use_one_native_account(self):
        first = self.provision()
        again = self.client.post(self.url, self.payload, format="json")
        self.assertEqual(again.status_code, 200)
        self.assertEqual(first, again.data)
        user = get_user_model().objects.get(pk=first["id"])
        self.assertEqual(user.profile.name, self.payload["name"])
        self.assertTrue(user.has_usable_password())
        self.assertIsNone(user.registration.activation_timestamp)
        self.assertFalse(user.is_staff or user.is_superuser)
        self.assertNotIn("password", first)
        self.assertEqual(ManagedAccount.objects.filter(user=user).count(), 1)

    def test_profile_update_preserves_password_and_identity(self):
        first = self.provision()
        user = get_user_model().objects.get(pk=first["id"])
        password = user.password
        response = self.client.patch(
            self.url, {"id": user.pk, "email": "updated@example.test", "name": "Updated Learner"}, format="json"
        )
        self.assertEqual(response.status_code, 200, response.data)
        user.refresh_from_db()
        self.assertEqual(user.password, password)
        self.assertEqual(user.username, first["username"])
        self.assertEqual(user.profile.name, "Updated Learner")
        self.assertEqual(user.email, "updated@example.test")

    def test_native_password_setup_generates_a_user_bound_recovery_link(self):
        from openedx.core.djangoapps.user_authn.views.password_reset import PasswordResetFormNoActive

        first = self.provision()
        user = get_user_model().objects.get(pk=first["id"])
        form = PasswordResetFormNoActive({"email": user.email})
        self.assertTrue(form.is_valid(), form.errors)
        request = RequestFactory().get("/")
        request.user = AnonymousUser()
        with patch("openedx.core.djangoapps.user_authn.views.password_reset.ace.send") as send:
            form.save(request=request, use_https=True)
        send.assert_called_once()
        message = send.call_args.args[0]
        self.assertEqual(message.recipient.email_address, user.email)
        uid, token = urlsplit(message.context["reset_link"]).path.rstrip("/").rsplit("/", 1)[1].split("-", 1)
        self.assertEqual(int(uid, 36), user.pk)
        self.assertTrue(default_token_generator.check_token(user, token))

    def test_revoked_service_permission_is_rechecked_before_mutation(self):
        self.provision()
        self.manager.user_permissions.clear()
        response = self.client.post(self.url, {**self.payload, "name": "Denied update"}, format="json")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            get_user_model().objects.get(username="sis_provisioning_test").profile.name, self.payload["name"]
        )

    def test_token_claims_do_not_create_or_reactivate_service_accounts(self):
        auth = ProvisioningAuthentication()
        for claims in (
            {"preferred_username": self.manager.username, "is_restricted": True},
            {"preferred_username": self.manager.username, "is_restricted": 0},
            {"preferred_username": "unknown_sis_service", "is_restricted": False},
        ):
            with self.subTest(claims=claims), self.assertRaises(AuthenticationFailed):
                auth.authenticate_credentials(claims)
        self.assertFalse(get_user_model().objects.filter(username="unknown_sis_service").exists())
        self.manager.is_active = False
        self.manager.save(update_fields=["is_active"])
        with self.assertRaises(AuthenticationFailed):
            auth.authenticate_credentials({"preferred_username": self.manager.username, "is_restricted": False})

    def test_ordinary_user_and_anonymous_cannot_provision(self):
        learner = get_user_model().objects.create_user(
            "provisioning_test_learner", email="provisioning-ordinary@example.test"
        )
        for user in (learner, None):
            self.client.force_authenticate(user)
            response = self.client.post(self.url, self.payload, format="json")
            self.assertIn(response.status_code, (401, 403))
        self.assertFalse(ManagedAccount.objects.filter(username="sis_provisioning_test").exists())

    def test_extra_privilege_fields_are_rejected(self):
        for field in ("is_staff", "is_superuser", "is_active", "password", "role"):
            response = self.client.post(self.url, {**self.payload, field: True}, format="json")
            self.assertEqual(response.status_code, 400)
        self.assertFalse(ManagedAccount.objects.filter(username="sis_provisioning_test").exists())

    def test_existing_user_is_not_implicitly_adopted(self):
        user = get_user_model().objects.create_user("sis_provisioning_test", email=self.payload["email"])
        response = self.client.post(self.url, self.payload, format="json")
        self.assertEqual(response.status_code, 409)
        self.assertFalse(ManagedAccount.objects.filter(user=user).exists())

    def test_other_service_cannot_update_or_retry_owned_account(self):
        self.provision()
        other = get_user_model().objects.create_user(
            "provisioning_other_service", email="provisioning-other@example.test"
        )
        other.user_permissions.add(*self.manager.user_permissions.all())
        self.client.force_authenticate(other)
        response = self.client.post(self.url, self.payload, format="json")
        self.assertEqual(response.status_code, 403)

    def test_disabled_account_is_not_reactivated_by_retry(self):
        first = self.provision()
        get_user_model().objects.filter(pk=first["id"]).update(is_active=False)
        response = self.client.post(self.url, self.payload, format="json")
        self.assertEqual(response.status_code, 409)
        self.assertFalse(get_user_model().objects.get(pk=first["id"]).is_active)

    def test_promoted_account_is_not_mutated(self):
        first = self.provision()
        get_user_model().objects.filter(pk=first["id"]).update(is_staff=True)
        response = self.client.patch(self.url, {**self.payload, "id": first["id"]}, format="json")
        self.assertEqual(response.status_code, 409)
        self.assertTrue(get_user_model().objects.get(pk=first["id"]).is_staff)

    def test_patch_requires_matching_remote_identity(self):
        first = self.provision()
        for identifier, expected in ((None, 400), (first["id"] + 1, 409)):
            payload = {**self.payload, "name": "Wrong identity"}
            if identifier is not None:
                payload["id"] = identifier
            response = self.client.patch(self.url, payload, format="json")
            self.assertEqual(response.status_code, expected)
        self.assertEqual(get_user_model().objects.get(pk=first["id"]).profile.name, self.payload["name"])

    def test_duplicate_email_is_not_merged(self):
        first = self.provision()
        response = self.client.post("/api/sis/v1/accounts/sis_second_test/", self.payload, format="json")
        self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(ManagedAccount.objects.filter(user_id=first["id"]).count(), 1)
        self.assertFalse(get_user_model().objects.filter(username="sis_second_test").exists())

    def test_explicit_legacy_binding_is_idempotent(self):
        from .accounts import create_account

        user = create_account("sis_provisioning_test", self.payload["email"], self.payload["name"])
        for _ in range(2):
            call_command(
                "sis_bind_account",
                manager=self.manager.username,
                username=user.username,
                confirm=True,
                stdout=StringIO(),
            )
        response = self.client.patch(self.url, {**self.payload, "id": user.pk}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(ManagedAccount.objects.get(user=user).manager_id, self.manager.pk)
