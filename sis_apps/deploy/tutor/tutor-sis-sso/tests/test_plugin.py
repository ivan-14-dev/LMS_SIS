import unittest

from jinja2 import Environment
from tutor_sis_sso.plugin import SETTINGS_PATCH, trusted_origins


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
