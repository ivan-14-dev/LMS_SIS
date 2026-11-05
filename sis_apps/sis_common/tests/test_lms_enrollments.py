from unittest import TestCase
from unittest.mock import Mock, call, patch
from urllib.parse import urlencode

import requests
from apps.integration.edx_client import EdxClient


class LMSEnrollmentContractTests(TestCase):
    course = "course-v1:SIS+QUALIFICATION+2026"
    endpoint = "https://lms.example.test/api/enrollment/v1/enrollments"

    def setUp(self):
        self.client = EdxClient(
            lms_url="https://lms.example.test",
            cms_url="https://studio.example.test",
            oauth_client_id="synthetic-client",
            oauth_client_secret="synthetic-secret",
        )
        self.client._access_token = "synthetic-token"
        self.client._token_expires_at = float("inf")
        self.enrollment = {
            "user": "learner",
            "course_details": {"course_id": self.course},
            "mode": "audit",
            "is_active": True,
        }

    @staticmethod
    def response(payload):
        response = Mock(spec=requests.Response)
        response.json.return_value = payload
        return response

    @patch("sis_common.lms_enrollments.requests.post")
    def test_enroll_posts_one_object_and_preserves_the_native_response(self, post):
        post.return_value = self.response(self.enrollment)
        assert self.client.enroll_user(self.course, "learner") == self.enrollment
        post.assert_called_once_with(
            "https://lms.example.test/api/enrollment/v1/enrollment",
            json=self.enrollment,
            headers=self.client._headers(),
            timeout=30,
            verify=True,
        )

    @patch("sis_common.lms_enrollments.requests.post")
    def test_unenrollment_updates_active_status_without_changing_the_mode(self, post):
        post.return_value = self.response({**self.enrollment, "is_active": False, "mode": "honor"})
        assert self.client.unenroll_user(self.course, "learner")
        assert post.call_args.kwargs["json"] == {
            "user": "learner",
            "course_details": {"course_id": self.course},
            "is_active": False,
        }
        post.return_value.raise_for_status.side_effect = requests.HTTPError("403 Forbidden")
        with self.assertRaises(requests.HTTPError):
            self.client.unenroll_user(self.course, "learner")

    @patch("sis_common.lms_enrollments.requests.post")
    def test_unconfirmed_enrollment_is_not_treated_as_success(self, post):
        for change in (
            {"user": "another-learner"},
            {"course_details": {"course_id": "another-course"}},
            {"is_active": False},
            {"mode": "honor"},
        ):
            with self.subTest(change=change):
                post.return_value = self.response({**self.enrollment, **change})
                with self.assertRaisesRegex(ValueError, "ne confirme pas"):
                    self.client.enroll_user(self.course, "learner")

    @patch("sis_common.lms_enrollments.requests.post")
    def test_bulk_enrollment_uses_individual_requests_in_input_order(self, post):
        another = {**self.enrollment, "user": "another-learner"}
        post.side_effect = [self.response(self.enrollment), self.response(another)]
        assert self.client.bulk_enroll(self.course, ["learner", "another-learner"]) == [self.enrollment, another]
        assert [request.kwargs["json"]["user"] for request in post.call_args_list] == ["learner", "another-learner"]

    @patch("sis_common.lms_enrollments.requests.get")
    def test_course_enrollments_collect_all_pages_with_the_course_filter(self, get):
        next_page = self.endpoint + "?" + urlencode({"course_id": self.course, "cursor": "next-page"})
        rows = [{"user": user, "course_id": self.course, "is_active": True} for user in ("first", "second")]
        get.side_effect = [
            self.response({"results": rows[:1], "next": next_page}),
            self.response({"results": rows[1:], "next": None}),
        ]
        assert self.client.get_enrollments(self.course) == rows
        assert get.call_args_list == [
            call(
                self.endpoint,
                params={"course_id": self.course},
                headers=self.client._headers(),
                timeout=30,
                verify=True,
            ),
            call(next_page, params=None, headers=self.client._headers(), timeout=30, verify=True),
        ]

    @patch("sis_common.lms_enrollments.requests.get")
    def test_pagination_does_not_send_credentials_outside_its_scope(self, get):
        for next_page in (
            "https://other.example.test/api/enrollment/v1/enrollments",
            self.endpoint + "?course_id=another-course&cursor=next",
            "http://lms.example.test/api/enrollment/v1/enrollments",
        ):
            with self.subTest(next_page=next_page):
                get.reset_mock()
                get.return_value = self.response({"results": [], "next": next_page})
                with self.assertRaisesRegex(ValueError, "périmètre"):
                    self.client.get_enrollments(self.course)
                assert get.call_count == 1

    @patch("sis_common.lms_enrollments.requests.get")
    def test_invalid_pages_and_pagination_cycles_raise(self, get):
        next_page = self.endpoint + "?" + urlencode({"course_id": self.course, "cursor": "repeated"})
        for payload in ({}, [], {"results": []}, {"results": [{"course_id": "another-course"}], "next": None}):
            with self.subTest(payload=payload):
                get.return_value = self.response(payload)
                with self.assertRaises(ValueError):
                    self.client.get_enrollments(self.course)
        get.reset_mock()
        get.return_value = self.response({"results": [], "next": next_page})
        with self.assertRaisesRegex(ValueError, "périmètre"):
            self.client.get_enrollments(self.course)
        assert get.call_count == 2

    @patch("sis_common.lms_enrollments.requests.post")
    def test_tls_configuration_applies_to_oauth_and_enrollment(self, post):
        self.client._access_token = None
        self.client.verify_ssl = False
        post.side_effect = [
            self.response({"access_token": "synthetic-token", "expires_in": 3600}),
            self.response(self.enrollment),
        ]
        self.client.enroll_user(self.course, "learner")
        assert len(post.call_args_list) == 2
        assert all(request.kwargs["verify"] is False for request in post.call_args_list)
        assert post.call_args_list[0].kwargs["data"]["asymmetric_jwt"] == "true"
