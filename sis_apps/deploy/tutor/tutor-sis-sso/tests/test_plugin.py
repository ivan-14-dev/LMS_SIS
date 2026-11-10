import unittest

from jinja2 import Environment
from tutor_sis_sso.plugin import SETTINGS_PATCH, grade_targets, trusted_origins


class TrustedOriginsTests(unittest.TestCase):
    def test_exact_origins_are_normalized_without_wildcards(self):
        self.assertEqual(
            trusted_origins(["https://SIS.example.test:443/", "https://sis.example.test"], True),
            ["https://sis.example.test"],
        )
        self.assertEqual(
            trusted_origins(["http://sis.lms.localhost:59082"], False),
            ["http://sis.lms.localhost:59082"],
        )

    def test_invalid_configuration_is_rejected_before_rendering(self):
        for value in (
            None,
            "https://sis.example.test",
            [None],
            ["*"],
            ["https://*.example.test"],
            ["https://user:password@sis.example.test"],
            ["https://sis.example.test/path"],
            ["https://sis.example.test?query=1"],
            ["https://sis.example.test#fragment"],
            ["https://sis.example.test\n"],
            ["https://sis.example.test:invalid"],
            ["http://sis.example.test"],
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                trusted_origins(value, True)

    def test_rendered_patch_preserves_native_origins_and_cookie_boundary(self):
        environment = Environment()
        environment.filters["sis_trusted_origins"] = trusted_origins
        environment.filters["sis_grade_targets"] = grade_targets
        patch = environment.from_string(SETTINGS_PATCH).render(
            SIS_SSO_ORIGINS=["https://sis.lms.example.test"], ENABLE_HTTPS=True
        )
        settings = {
            "LOGIN_REDIRECT_WHITELIST": ["apps.lms.example.test"],
            "CORS_ORIGIN_WHITELIST": ["https://apps.lms.example.test"],
            "CSRF_TRUSTED_ORIGINS": ["https://apps.lms.example.test"],
            "SESSION_COOKIE_DOMAIN": "lms.example.test",
        }
        exec(compile(patch, "<sis-sso-settings>", "exec"), settings)
        self.assertEqual(settings["SESSION_COOKIE_DOMAIN"], "lms.example.test")
        self.assertEqual(
            settings["LOGIN_REDIRECT_WHITELIST"],
            ["apps.lms.example.test", "sis.lms.example.test"],
        )
        for name in ("CORS_ORIGIN_WHITELIST", "CSRF_TRUSTED_ORIGINS"):
            self.assertEqual(
                settings[name],
                ["https://apps.lms.example.test", "https://sis.lms.example.test"],
            )


class GradeCallbackSettingsTests(unittest.TestCase):
    def test_empty_targets_preserve_native_grade_configuration(self):
        environment = Environment()
        environment.filters.update(sis_trusted_origins=trusted_origins, sis_grade_targets=grade_targets)
        settings = {
            "LOGIN_REDIRECT_WHITELIST": [],
            "CORS_ORIGIN_WHITELIST": [],
            "CSRF_TRUSTED_ORIGINS": [],
            "SIS_GRADE_WEBHOOK_TARGETS": [{"url": "https://native.example.test/"}],
            "FEATURES": {"ENABLE_COURSE_ASSESSMENT_GRADE_CHANGE_SIGNAL": True},
            "INSTALLED_APPS": ["existing.app"],
        }
        rendered = environment.from_string(SETTINGS_PATCH).render(
            SIS_SSO_ORIGINS=[], ENABLE_HTTPS=True, SIS_GRADE_WEBHOOK_TARGETS=[]
        )
        exec(compile(rendered, "<sis-grade-settings>", "exec"), settings)
        self.assertEqual(settings["SIS_GRADE_WEBHOOK_TARGETS"], [{"url": "https://native.example.test/"}])
        self.assertEqual(settings["FEATURES"], {"ENABLE_COURSE_ASSESSMENT_GRADE_CHANGE_SIGNAL": True})
        self.assertEqual(settings["INSTALLED_APPS"], ["existing.app"])

    def test_invalid_targets_are_rejected_without_exposing_the_secret(self):
        secret = "private-test-value"
        for target in (
            {"url": "http://sis.example.test/webhook/", "secret": secret},
            {"url": "https://name:password@sis.example.test/", "secret": secret},
            {"url": "https://*.example.test/", "secret": secret},
            {"url": "https://sis.example.test/#fragment", "secret": secret},
            {"url": "https://sis.example.test:invalid/", "secret": secret},
            {"url": f"https://sis.example.test:{secret}/", "secret": secret},
            {"url": "https://sis.example.test/", "secret": ""},
            {"url": "https://sis.example.test/", "secret": secret, "course_ids": "course-v1:Org+Course+Run"},
            {"url": "https://sis.example.test/", "secret": secret, "course_id": "misspelled-field"},
            None,
        ):
            with self.subTest(target_type=type(target).__name__), self.assertRaises(ValueError) as error:
                grade_targets([target])
            self.assertNotIn(secret, str(error.exception))

    def test_rendered_targets_enable_the_native_receiver_without_duplicate_app(self):
        environment = Environment()
        environment.filters.update(sis_trusted_origins=trusted_origins, sis_grade_targets=grade_targets)
        app = "openedx.core.djangoapps.sis_grade_webhooks.apps.SisGradeWebhooksConfig"
        target = {
            "url": "https://sis.example.test:8443/api/v1/integration/webhook/lms/",
            "secret": "private-test-value",
            "course_ids": ["course-v1:Org+Course+Run"],
        }
        rendered = environment.from_string(SETTINGS_PATCH).render(
            SIS_SSO_ORIGINS=[], ENABLE_HTTPS=False, SIS_GRADE_WEBHOOK_TARGETS=[target]
        )
        for installed in ([], [app]):
            settings = {
                "LOGIN_REDIRECT_WHITELIST": [],
                "CORS_ORIGIN_WHITELIST": [],
                "CSRF_TRUSTED_ORIGINS": [],
                "INSTALLED_APPS": installed,
                "FEATURES": {"existing_feature": True},
            }
            exec(compile(rendered, "<sis-grade-settings>", "exec"), settings)
            self.assertEqual(settings["INSTALLED_APPS"], [app])
            self.assertEqual(settings["SIS_GRADE_WEBHOOK_TARGETS"], [target])
            self.assertEqual(
                settings["FEATURES"],
                {
                    "existing_feature": True,
                    "ENABLE_COURSE_ASSESSMENT_GRADE_CHANGE_SIGNAL": True,
                },
            )
