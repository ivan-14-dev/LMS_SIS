from unittest import TestCase
from unittest.mock import Mock, patch

from apps.integration.edx_client import EdxClient


class EdxClientContractTestCase(TestCase):
    def setUp(self):
        self.client = EdxClient(
            lms_url="https://lms.example.test",
            cms_url="https://studio.example.test",
            oauth_client_id="client",
            oauth_client_secret="secret",
        )
        self.client._access_token = "token"
        self.client._token_expires_at = float("inf")

    @patch("apps.integration.edx_client.requests.get")
    def test_get_grades_uses_course_grades_contract(self, request_get):
        response = Mock()
        response.json.return_value = [{"username": "learner", "percent": 0.75}]
        request_get.return_value = response

        result = self.client.get_grades("course-v1:Org+Course+Run", "learner")

        assert result["percent"] == 0.75
        request_get.assert_called_once_with(
            "https://lms.example.test/api/grades/v1/courses/"
            "course-v1:Org+Course+Run/",
            params={"username": "learner"},
            headers=self.client._headers(),
            timeout=30,
        )

    @patch("apps.integration.edx_client.requests.post")
    def test_configure_course_live_translates_bigbluebutton_provider(
        self, request_post
    ):
        response = Mock()
        response.json.return_value = {
            "provider_type": "big_blue_button",
            "enabled": True,
        }
        request_post.return_value = response

        result = self.client.configure_course_live(
            "course-v1:Org+Course+Run", "bigbluebutton"
        )

        assert result["provider_type"] == "big_blue_button"
        payload = request_post.call_args.kwargs["json"]
        assert payload["provider_type"] == "big_blue_button"
        assert payload["free_tier"]
        assert "secret" not in payload
