from unittest import TestCase
from unittest.mock import Mock, patch

import requests
from apps.integration.edx_client import EdxClient


class LMSAccountContractTests(TestCase):
    def setUp(self):
        self.client = EdxClient(
            lms_url="https://lms.example.test",
            cms_url="https://studio.example.test",
            oauth_client_id="synthetic-client",
            oauth_client_secret="synthetic-secret",
        )
        self.client._access_token = "synthetic-token"
        self.client._token_expires_at = float("inf")
        self.account = {
            "id": 101,
            "username": "sis_learner",
            "email": "learner@example.test",
            "name": "Synthetic Learner",
            "is_active": True,
            "is_staff": False,
            "is_superuser": False,
        }

    def response(self, **changes):
        response = Mock(spec=requests.Response)
        response.status_code = 200
        response.json.return_value = {**self.account, **changes}
        return response

    @patch("sis_common.lms_accounts.requests.post")
    def test_creation_uses_installed_extension_without_privileges_or_password(self, post):
        post.return_value = self.response()
        self.assertEqual(
            self.client.create_user("sis_learner", "learner@example.test", "Synthetic Learner", role="teacher"),
            self.account,
        )
        post.assert_called_once_with(
            "https://lms.example.test/api/sis/v1/accounts/sis_learner/",
            json={"email": "learner@example.test", "name": "Synthetic Learner"},
            headers=self.client._headers(),
            timeout=30,
            verify=True,
            allow_redirects=False,
        )

    @patch("sis_common.lms_accounts.requests.patch")
    def test_update_requires_the_existing_remote_id_and_respects_tls(self, patch_account):
        patch_account.return_value = self.response()
        self.client.verify_ssl = False
        self.client.update_user(
            "sis_learner", {"email": "learner@example.test", "name": "Synthetic Learner"}, user_id=101
        )
        self.assertEqual(patch_account.call_args.kwargs["json"]["id"], 101)
        self.assertFalse(patch_account.call_args.kwargs["verify"])
        patch_account.return_value = self.response(id=102)
        with self.assertRaisesRegex(ValueError, "identité"):
            self.client.update_user(
                "sis_learner", {"email": "learner@example.test", "name": "Synthetic Learner"}, user_id=101
            )

    @patch("sis_common.lms_accounts.requests.post")
    def test_privilege_requests_are_rejected_without_http(self, post):
        for options in (
            {"is_staff": True},
            {"is_superuser": True},
            {"role": "admin"},
            {"extra": {"password": "not-transmitted"}},
        ):
            with self.subTest(options=options), self.assertRaises(ValueError):
                self.client.create_user("sis_learner", "learner@example.test", "Synthetic Learner", **options)
        post.assert_not_called()

    @patch("sis_common.lms_accounts.requests.post")
    def test_incomplete_foreign_or_privileged_confirmation_is_rejected(self, post):
        for change in (
            {"id": None},
            {"id": True},
            {"username": "someone_else"},
            {"email": "someone-else@example.test"},
            {"name": "Another Learner"},
            {"is_active": False},
            {"is_staff": True},
            {"is_superuser": True},
        ):
            post.return_value = self.response(**change)
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, "identité"):
                self.client.create_user("sis_learner", "learner@example.test", "Synthetic Learner")

    @patch("sis_common.lms_accounts.requests.post")
    def test_missing_extension_errors_and_redirects_are_not_successes(self, post):
        post.return_value = self.response()
        post.return_value.raise_for_status.side_effect = requests.HTTPError("404 extension missing")
        with self.assertRaises(requests.HTTPError):
            self.client.create_user("sis_learner", "learner@example.test", "Synthetic Learner")
        post.return_value = self.response()
        post.return_value.status_code = 302
        with self.assertRaisesRegex(ValueError, "provisioning"):
            self.client.create_user("sis_learner", "learner@example.test", "Synthetic Learner")
