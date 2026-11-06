import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from scripts import sisctl


class CardReferencePreflightTests(unittest.TestCase):
    def test_scans_both_variants_and_reports_duplicate_ids_without_references(self):
        queries = []

        def fake_compose(_configuration, *arguments, **_kwargs):
            self.assertEqual(arguments[:2], ("exec", "-T"))
            self.assertIn("-w", arguments)
            service = arguments[2]
            sql = arguments[-1]
            queries.append((service, sql))
            if "FROM pg_catalog.pg_namespace" in sql:
                schemas = "school_a\nschool_b\n" if service == "postgres-secondaire" else "campus_a\n"
                return SimpleNamespace(stdout=schemas)
            if '"school_a"."paiements_paiement"' in sql:
                return SimpleNamespace(stdout='{"count": 0, "samples": []}\n')
            if '"school_b"."paiements_paiement"' in sql:
                return SimpleNamespace(stdout='{"count": 1, "samples": [[17, 22]]}\n')
            return SimpleNamespace(stdout='{"count": 1, "samples": [[7, 9]]}\n')

        with patch.object(sisctl, "compose", side_effect=fake_compose):
            with self.assertRaises(ValueError) as error:
                sisctl.preflight_card_references({"SIS_MODE": "dual"})
        self.assertIn("secondaire/school_b: 1", str(error.exception))
        self.assertIn("superieur/campus_a: 1", str(error.exception))
        self.assertIn("17, 22", str(error.exception))
        self.assertIn("7, 9", str(error.exception))
        self.assertNotIn("pi_", str(error.exception))
        self.assertIn("statut IN ('valide', 'rembourse')", queries[1][1])
        self.assertIn("reference_externe <> ''", queries[1][1])
        self.assertIn('"campus_a"."paiements_paiementfrais"', queries[-1][1])
        self.assertEqual(len(queries), 5)

    def test_empty_database_and_no_conflicts_pass(self):
        def fake_compose(_configuration, *arguments, **_kwargs):
            if "FROM pg_catalog.pg_namespace" in arguments[-1]:
                return SimpleNamespace(stdout="existing_tenant\n" if arguments[2] == "postgres-secondaire" else "")
            return SimpleNamespace(stdout='{"count": 0, "samples": []}\n')

        with patch.object(sisctl, "compose", side_effect=fake_compose):
            sisctl.preflight_card_references({"SIS_MODE": "dual"})

    def test_database_read_failure_is_not_treated_as_clean(self):
        with patch.object(
            sisctl, "compose",
            side_effect=subprocess.CalledProcessError(1, ["psql"]),
        ):
            with self.assertRaisesRegex(ValueError, "No migration was attempted"):
                sisctl.preflight_card_references({"SIS_MODE": "secondaire"})

    def test_init_aborts_before_bootstrap_on_duplicate_refs(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            institution = Path(directory) / "institution.json"
            institution.write_text(json.dumps({
                "schema_name": "school_a", "domain": "school-a.example.test",
                "institution": {}, "admin": {},
            }), encoding="utf-8")
            calls = []

            def fake_compose(_configuration, *arguments, **_kwargs):
                calls.append(arguments)
                if "FROM pg_catalog.pg_namespace" in arguments[-1]:
                    return SimpleNamespace(stdout="school_a\n")
                if arguments[:2] == ("exec", "-T"):
                    return SimpleNamespace(stdout='{"count": 1, "samples": [[17, 22]]}\n')
                return SimpleNamespace()

            with patch.object(sisctl, "compose", side_effect=fake_compose), patch.object(
                sisctl.getpass, "getpass", side_effect=AssertionError("Password prompt must not run"),
            ):
                with self.assertRaisesRegex(ValueError, "school_a"):
                    sisctl.initialize(
                        {"SIS_MODE": "secondaire"},
                        SimpleNamespace(variant="secondaire", institution=institution),
                    )

        self.assertEqual([call[:2] for call in calls[:3]], [
            ("config", "--quiet"), ("build", "api-secondaire"), ("up", "-d"),
        ])
        self.assertFalse(any(call[0] == "run" for call in calls))

    def test_init_rejects_malformed_institution_before_compose_or_password_prompt(self):
        with tempfile.TemporaryDirectory() as directory:
            institution = Path(directory) / "institution.json"
            for content in (
                [],
                {"schema_name": "school_a"},
                {
                    "schema_name": "school_a", "domain": "school-a.example.test",
                    "institution": [], "admin": {},
                },
            ):
                with self.subTest(content=content):
                    institution.write_text(json.dumps(content), encoding="utf-8")
                    with patch.object(
                        sisctl, "compose", side_effect=AssertionError("Must not start Compose")
                    ), patch.object(
                        sisctl.getpass, "getpass", side_effect=AssertionError("Must not prompt")
                    ):
                        with self.assertRaisesRegex(ValueError, "Institution JSON requires"):
                            sisctl.initialize(
                                {"SIS_MODE": "secondaire"},
                                SimpleNamespace(variant="secondaire", institution=institution),
                            )


class InitSchemaPreflightTests(unittest.TestCase):
    def options(self, schema, variant):
        institution = Mock(spec=Path)
        institution.resolve.return_value = institution
        institution.read_text.return_value = json.dumps({
            "schema_name": schema,
            "domain": "school.example.test",
            "institution": {"nom": "School"},
            "admin": {"username": "admin", "email": "admin@example.test"},
        })
        return SimpleNamespace(variant=variant, institution=institution)

    def test_rejects_reserved_or_invalid_schema_before_effects_or_password_prompt(self):
        for variant in ("secondaire", "superieur"):
            for schema in ("public", "", "School_a", "school-a", "_school", "1school", "a" * 64, "school\n"):
                with self.subTest(variant=variant, schema=schema):
                    options = self.options(schema, variant)
                    configuration = {"SIS_MODE": variant}
                    with patch.object(sisctl, "compose") as compose, patch.object(
                        sisctl, "preflight_card_references",
                    ) as preflight, patch.object(sisctl.getpass, "getpass", return_value="unused") as prompt:
                        with self.assertRaisesRegex(ValueError, "schema_name.*non-public.*lowercase"):
                            sisctl.initialize(configuration, options)
                        compose.assert_not_called()
                        preflight.assert_not_called()
                        prompt.assert_not_called()
                    self.assertEqual(configuration, {"SIS_MODE": variant})

    def test_accepts_valid_schema_boundaries_for_both_variants(self):
        for variant in ("secondaire", "superieur"):
            for schema in ("a", "school_1", "a" * 63):
                with self.subTest(variant=variant, schema=schema):
                    options = self.options(schema, variant)
                    configuration = {"SIS_MODE": "dual"}
                    with patch.object(sisctl, "compose") as compose, patch.object(
                        sisctl, "preflight_card_references",
                    ) as preflight, patch.object(sisctl.getpass, "getpass", return_value="test-only") as prompt:
                        sisctl.initialize(configuration, options)
                    preflight.assert_called_once_with({"SIS_MODE": variant})
                    prompt.assert_called_once()
                    self.assertEqual(compose.call_count, 5)
                    bootstrap = compose.call_args_list[3]
                    self.assertIn(f"api-{variant}", bootstrap.args)
                    self.assertIn("bootstrap_institution", bootstrap.args)
                    self.assertEqual(bootstrap.kwargs["input"], b"test-only\n")


class ConfigureSafetyTests(unittest.TestCase):
    def options(self, directory, keys):
        jwks = Path(directory) / "public-jwks.json"
        jwks.write_text(json.dumps({"keys": keys}), encoding="utf-8")
        return SimpleNamespace(
            env_file=Path(directory) / ".env",
            domain="school.example",
            local=False,
            lms_url="https://lms.school.example",
            cms_url="https://studio.school.example",
            jwks=jwks,
            mode="secondaire",
            auth_mode="lms",
            oauth_client_id="sis-test",
            issuer=None,
            audience="openedx",
        )

    def test_refuses_private_rsa_material_and_incomplete_public_keys_before_prompting(self):
        public = {"kty": "RSA", "n": "AQAB", "e": "AQAB"}
        with tempfile.TemporaryDirectory() as directory:
            for field in ("d", "p", "q", "dp", "dq", "qi", "oth"):
                with self.subTest(field=field):
                    options = self.options(directory, [{**public, field: "private"}])
                    with patch.object(sisctl.getpass, "getpass", side_effect=AssertionError("Must not prompt")):
                        with self.assertRaisesRegex(ValueError, "Only public RSA"):
                            sisctl.configure(options)
                    self.assertFalse(options.env_file.exists())
            for field in ("n", "e"):
                with self.subTest(missing=field):
                    options = self.options(directory, [{key: value for key, value in public.items() if key != field}])
                    with patch.object(sisctl.getpass, "getpass", side_effect=AssertionError("Must not prompt")):
                        with self.assertRaisesRegex(ValueError, "Only public RSA"):
                            sisctl.configure(options)
                    self.assertFalse(options.env_file.exists())

    def test_accepts_public_rsa_jwks_without_private_fields(self):
        public = {"kty": "RSA", "kid": "sis-signing", "n": "AQAB", "e": "AQAB"}
        with tempfile.TemporaryDirectory() as directory:
            options = self.options(directory, [public])
            with patch.object(sisctl.getpass, "getpass", return_value="throwaway-test-only"):
                sisctl.configure(options)
            saved = sisctl.read_configuration(options.env_file)
            self.assertEqual(json.loads(saved["EDX_JWT_PUBLIC_SIGNING_JWK_SET"]), {"keys": [public]})
            self.assertEqual(options.env_file.stat().st_mode & 0o777, 0o600)

    def test_refuses_incomplete_lms_or_insecure_studio_urls_before_prompting(self):
        public = {"kty": "RSA", "n": "AQAB", "e": "AQAB"}
        with tempfile.TemporaryDirectory() as directory:
            for url in ("https://", "https://lms.school.example/oauth2", "https://user@lms.school.example"):
                with self.subTest(lms=url):
                    options = self.options(directory, [public])
                    options.lms_url = url
                    with patch.object(sisctl.getpass, "getpass", side_effect=AssertionError("Must not prompt")):
                        with self.assertRaisesRegex(ValueError, "LMS URL"):
                            sisctl.configure(options)
                    self.assertFalse(options.env_file.exists())
            for url in ("http://studio.school.example", "https://", "https://studio.school.example/?key=value"):
                with self.subTest(studio=url):
                    options = self.options(directory, [public])
                    options.cms_url = url
                    with patch.object(sisctl.getpass, "getpass", side_effect=AssertionError("Must not prompt")):
                        with self.assertRaisesRegex(ValueError, "Studio URL"):
                            sisctl.configure(options)
                    self.assertFalse(options.env_file.exists())

    def test_local_mode_accepts_explicit_http_origins(self):
        public = {"kty": "RSA", "n": "AQAB", "e": "AQAB"}
        with tempfile.TemporaryDirectory() as directory:
            options = self.options(directory, [public])
            options.local = True
            options.lms_url = "http://lms.localhost:59080/"
            options.cms_url = "http://studio.localhost:59080/"
            with patch.object(sisctl.getpass, "getpass", return_value="throwaway-test-only"):
                sisctl.configure(options)
            saved = sisctl.read_configuration(options.env_file)
            self.assertEqual(saved["EDX_LMS_URL"], "http://lms.localhost:59080")
            self.assertEqual(saved["EDX_CMS_URL"], "http://studio.localhost:59080")


if __name__ == "__main__":
    unittest.main()
