"""HTTP simulations only: no Django, broker, database or external LMS required."""

from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

import requests

from sis_common.lms_diagnostics import check_health, integration_health


class LMSDiagnosticsTests(TestCase):
    def setUp(self):
        self.settings = SimpleNamespace(
            EDX_LMS_URL="https://lms.example.test", EDX_CMS_URL="https://studio.example.test",
            EDX_OAUTH_CLIENT_ID="synthetic-client", EDX_OAUTH_CLIENT_SECRET="synthetic-secret",
        )
        self.client = SimpleNamespace(
            lms_url=self.settings.EDX_LMS_URL, cms_url=self.settings.EDX_CMS_URL,
            verify_ssl=True, _headers=Mock(return_value={"Authorization": "JWT synthetic-token"}),
        )
        self.client.health_check = lambda: check_health(self.client)

    def response(self, status=200, **changes):
        return Mock(
            status_code=status,
            json=Mock(return_value={
                "contract": "sis-provisioning/v1",
                "capabilities": {
                    "accounts": True, "enrollments": True, "teaching": True,
                    "courses": True, "publication": True,
                },
                **changes,
            }),
        )

    def test_unconfigured_provider_never_constructs_client_or_calls_http(self):
        factory = Mock()
        self.settings.EDX_OAUTH_CLIENT_SECRET = ""
        report = integration_health(self.settings, factory)
        assert not report["available"]
        assert not report["configured"]
        assert report["missing_configuration"] == ["EDX_OAUTH_CLIENT_SECRET"]
        assert report["oauth_status"] == "unavailable"
        factory.assert_not_called()
        assert "synthetic-secret" not in str(report)

    @patch("sis_common.lms_diagnostics.requests.get")
    def test_heartbeat_without_extension_is_unavailable(self, get):
        get.side_effect = [self.response(), self.response(404), self.response(), self.response(404)]
        report = integration_health(self.settings, lambda: self.client)
        assert not report["connected"]
        assert not report["available"]
        assert report["lms"]["contract_http_status"] == 404
        assert report["webhook_status"] == "unverified"

    @patch("sis_common.lms_diagnostics.requests.get")
    def test_both_authenticated_contracts_are_required_not_webhook_or_pedagogy_proof(self, get):
        get.return_value = self.response()
        report = integration_health(self.settings, lambda: self.client)
        assert report["connected"]
        assert report["oauth_status"] == "valid"
        assert report["webhook_status"] == "unverified"
        assert get.call_count == 4
        for call in get.call_args_list:
            assert call.kwargs["verify"]
            assert not call.kwargs["allow_redirects"]
        assert "Authorization" in get.call_args_list[1].kwargs["headers"]

    @patch("sis_common.lms_diagnostics.requests.get")
    def test_missing_permissions_wrong_contract_and_redirects_fail_closed(self, get):
        for response in (
            self.response(capabilities={"accounts": True}),
            self.response(capabilities={"accounts": 1, "enrollments": True, "teaching": True}),
            self.response(contract="unknown"),
            self.response(302),
            self.response(403),
        ):
            with self.subTest(response=response):
                get.side_effect = [self.response(), response, self.response(), self.response()]
                report = integration_health(self.settings, lambda: self.client)
                assert not report["available"]

    @patch("sis_common.lms_diagnostics.requests.get")
    def test_network_and_oauth_errors_never_leak_raw_responses(self, get):
        get.side_effect = requests.ConnectionError("synthetic-secret in upstream response")
        report = integration_health(self.settings, lambda: self.client)
        assert not report["connected"]
        assert "synthetic-secret" not in str(report)
        get.side_effect = None
        get.return_value = self.response()
        self.client._headers.side_effect = KeyError("synthetic-secret")
        report = integration_health(self.settings, lambda: self.client)
        assert not report["connected"]
        assert "synthetic-secret" not in str(report)

    def test_legacy_boolean_heartbeat_result_is_not_a_contract_confirmation(self):
        self.client.health_check = lambda: {"lms": True, "cms": True}
        assert not integration_health(self.settings, lambda: self.client)["connected"]

    def test_diagnostic_urls_do_not_expose_embedded_credentials_or_query_values(self):
        self.settings.EDX_LMS_URL = "https://service:synthetic-secret@lms.example.test:8443/path?token=hidden"
        self.settings.EDX_OAUTH_CLIENT_SECRET = ""
        report = integration_health(self.settings, Mock())
        assert report["lms_url"] == "https://lms.example.test:8443"
        assert "synthetic-secret" not in str(report)
        assert "hidden" not in str(report)
