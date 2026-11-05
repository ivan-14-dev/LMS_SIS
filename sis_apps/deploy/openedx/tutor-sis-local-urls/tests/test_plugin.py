import unittest
from pathlib import Path

from jinja2 import Environment, StrictUndefined
from tutor import hooks
import yaml

from tutor_sis_local_urls.plugin import (
    CADDY_PATCH, INDIGO_ASSETS_PATCH, PREAMBLE, hostname, local_hosts, normalize_init_callbacks, settings_patch,
)


class LocalURLsTests(unittest.TestCase):
    def setUp(self):
        self.config = {
            "SIS_LOCAL_URLS_ENABLED": True,
            "SIS_LOCAL_URLS_PORT": 59080,
            "ENABLE_HTTPS": False,
            "ENABLE_WEB_PROXY": False,
            "CADDY_HTTP_PORT": "127.0.0.1:59080",
            "LMS_HOST": "lms.sis.localhost:59080",
            "CMS_HOST": "studio.lms.sis.localhost:59080",
            "MFE_HOST": "apps.lms.sis.localhost:59080",
            "MEILISEARCH_HOST": "meilisearch.lms.sis.localhost:59080",
            "PLUGINS": ["mfe", "indigo", "sis_local_urls"],
        }
        self.environment = Environment(undefined=StrictUndefined)
        self.environment.globals["sis_local_urls"] = local_hosts
        self.environment.filters["sis_local_hostname"] = hostname

    def render(self, template):
        return self.environment.from_string(template).render(self.config)

    def test_default_off_preserves_existing_settings(self):
        self.config.update(SIS_LOCAL_URLS_ENABLED=False, ENABLE_HTTPS=True, LMS_HOST="lms.example.org")
        original = {"ALLOWED_HOSTS": ["original"], "SESSION_COOKIE_DOMAIN": "original"}
        settings = dict(original)
        exec(self.render(settings_patch("lms")), settings)
        for key, value in original.items():
            self.assertEqual(settings[key], value)
        self.assertEqual(self.render(CADDY_PATCH).strip(), "")

    def test_rejects_nonlocal_or_inconsistent_origins(self):
        for key, value in [
            ("SIS_LOCAL_URLS_ENABLED", "true"),
            ("SIS_LOCAL_URLS_PORT", 80),
            ("SIS_LOCAL_URLS_PORT", True),
            ("SIS_LOCAL_URLS_PORT", 65536),
            ("ENABLE_HTTPS", True),
            ("ENABLE_WEB_PROXY", True),
            ("CADDY_HTTP_PORT", "0.0.0.0:59080"),
            ("LMS_HOST", "lms.example.org:59080"),
            ("LMS_HOST", "lms.localhost.example.org:59080"),
            ("CMS_HOST", "studio.lms.sis.localhost:59081"),
            ("MFE_HOST", "http://apps.lms.sis.localhost:59080"),
            ("MFE_HOST", "apps.lms.sis.localhost"),
            ("MFE_HOST", "user@apps.localhost:59080"),
            ("MEILISEARCH_HOST", "meili..localhost:59080"),
        ]:
            with self.subTest(key=key, value=value):
                old = self.config[key]
                self.config[key] = value
                with self.assertRaises(ValueError):
                    self.render(PREAMBLE)
                self.config[key] = old

    def test_runtime_domains_and_compose_use_same_port_without_widening_cookies(self):
        for service, expected in (("lms", "lms.sis.localhost"), ("cms", "studio.lms.sis.localhost")):
            settings = {}
            exec(self.render(settings_patch(service)), settings)
            self.assertEqual(settings["ALLOWED_HOSTS"], [expected, service])
            self.assertEqual(settings["SESSION_COOKIE_DOMAIN"], expected)
            self.assertEqual(settings["SHARED_COOKIE_DOMAIN"], expected)
        template = Path(__file__).parents[1] / "tutor_sis_local_urls/templates/local/docker-compose.prod.override.yml"
        class Loader(yaml.SafeLoader):
            pass
        Loader.add_constructor("!override", lambda loader, node: loader.construct_sequence(node))
        compose = yaml.load(self.render(template.read_text()), Loader=Loader)
        caddy = compose["services"]["caddy"]
        self.assertEqual(caddy["ports"], ["127.0.0.1:59080:59080"])
        self.assertEqual(caddy["environment"]["default_site_port"], "")
        self.assertEqual(caddy["networks"]["default"]["aliases"], [
            "lms.sis.localhost", "studio.lms.sis.localhost",
            "apps.lms.sis.localhost", "meilisearch.lms.sis.localhost",
        ])
        self.assertIn("http_port 59080", self.render(CADDY_PATCH))
        self.config["SIS_LOCAL_URLS_ENABLED"] = False
        self.assertEqual(yaml.safe_load(self.render(template.read_text())), {"services": {}})

    def test_init_normalizes_only_development_callback_and_preserves_disabled_behavior(self):
        script = 'prod=http://{{ CMS_HOST }}/complete/edx-oauth2/ dev=http://{{ CMS_HOST }}:8001/complete/edx-oauth2/'
        tasks = normalize_init_callbacks([("lms", script), ("cms", "unchanged")])
        self.assertEqual(tasks[1], ("cms", "unchanged"))
        self.assertEqual(self.render(tasks[0][1]), (
            "prod=http://studio.lms.sis.localhost:59080/complete/edx-oauth2/ "
            "dev=http://studio.lms.sis.localhost:8001/complete/edx-oauth2/"
        ))
        self.config.update(SIS_LOCAL_URLS_ENABLED=False, CMS_HOST="studio.example.org")
        self.assertEqual(self.render(tasks[0][1]), self.render(script))

    def test_lms_only_initialization_applies_callback_normalization(self):
        script = 'http://{{ CMS_HOST }}:8001/complete/edx-oauth2/'
        with hooks.Contexts.app("lms").enter():
            hooks.Filters.CLI_DO_INIT_TASKS.add_item(("lms", script))
        scripts = [
            self.render(task)
            for service, task in hooks.Filters.CLI_DO_INIT_TASKS.iterate_from_context(hooks.Contexts.app("lms").name)
            if service == "lms"
        ]
        self.assertIn("http://studio.lms.sis.localhost:8001/complete/edx-oauth2/", scripts)
        self.assertNotIn("http://studio.lms.sis.localhost:59080:8001/complete/edx-oauth2/", scripts)

    def test_indigo_logo_aliases_only_rewrite_the_two_existing_image_paths(self):
        patch = self.render(INDIGO_ASSETS_PATCH)
        self.assertEqual(
            [line for line in patch.splitlines() if line.startswith("rewrite ")],
            [
                "rewrite /static/images/tutor-logo.png /static/indigo/images/tutor-logo.png",
                "rewrite /static/images/openedx-logo.png /static/indigo/images/openedx-logo.png",
            ],
        )
        self.config["PLUGINS"] = ["mfe", "sis_local_urls"]
        self.assertEqual(self.render(INDIGO_ASSETS_PATCH).strip(), "")
        self.config.update(SIS_LOCAL_URLS_ENABLED=False, PLUGINS=["mfe", "indigo"])
        self.assertEqual(self.render(INDIGO_ASSETS_PATCH).strip(), "")
