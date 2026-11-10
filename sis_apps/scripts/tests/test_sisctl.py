import json
import os
import socket
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
            sisctl,
            "compose",
            side_effect=subprocess.CalledProcessError(1, ["psql"]),
        ):
            with self.assertRaisesRegex(ValueError, "No migration was attempted"):
                sisctl.preflight_card_references({"SIS_MODE": "secondaire"})

    def test_init_aborts_before_bootstrap_on_duplicate_refs(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            institution = Path(directory) / "institution.json"
            institution.write_text(
                json.dumps(
                    {
                        "schema_name": "school_a",
                        "domain": "school-a.example.test",
                        "institution": {},
                        "admin": {},
                    }
                ),
                encoding="utf-8",
            )
            calls = []

            def fake_compose(_configuration, *arguments, **_kwargs):
                calls.append(arguments)
                if "FROM pg_catalog.pg_namespace" in arguments[-1]:
                    return SimpleNamespace(stdout="school_a\n")
                if arguments[:2] == ("exec", "-T"):
                    return SimpleNamespace(stdout='{"count": 1, "samples": [[17, 22]]}\n')
                return SimpleNamespace()

            with (
                patch.object(sisctl, "compose", side_effect=fake_compose),
                patch.object(
                    sisctl.getpass,
                    "getpass",
                    side_effect=AssertionError("Password prompt must not run"),
                ),
            ):
                with self.assertRaisesRegex(ValueError, "school_a"):
                    sisctl.initialize(
                        {"SIS_MODE": "secondaire"},
                        SimpleNamespace(variant="secondaire", institution=institution),
                    )

        self.assertEqual(
            [call[:2] for call in calls[:3]],
            [
                ("config", "--quiet"),
                ("build", "api-secondaire"),
                ("up", "-d"),
            ],
        )
        self.assertFalse(any(call[0] == "run" for call in calls))

    def test_init_rejects_malformed_institution_before_compose_or_password_prompt(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            institution = Path(directory) / "institution.json"
            for content in (
                [],
                {"schema_name": "school_a"},
                {
                    "schema_name": "school_a",
                    "domain": "school-a.example.test",
                    "institution": [],
                    "admin": {},
                },
            ):
                with self.subTest(content=content):
                    institution.write_text(json.dumps(content), encoding="utf-8")
                    with (
                        patch.object(sisctl, "compose", side_effect=AssertionError("Must not start Compose")),
                        patch.object(sisctl.getpass, "getpass", side_effect=AssertionError("Must not prompt")),
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
        institution.read_text.return_value = json.dumps(
            {
                "schema_name": schema,
                "domain": "school.example.test",
                "institution": {"nom": "School"},
                "admin": {"username": "admin", "email": "admin@example.test"},
            }
        )
        return SimpleNamespace(variant=variant, institution=institution)

    def test_rejects_reserved_or_invalid_schema_before_effects_or_password_prompt(self):
        for variant in ("secondaire", "superieur"):
            for schema in ("public", "", "School_a", "school-a", "_school", "1school", "a" * 64, "school\n"):
                with self.subTest(variant=variant, schema=schema):
                    options = self.options(schema, variant)
                    configuration = {"SIS_MODE": variant}
                    with (
                        patch.object(sisctl, "compose") as compose,
                        patch.object(
                            sisctl,
                            "preflight_card_references",
                        ) as preflight,
                        patch.object(sisctl.getpass, "getpass", return_value="unused") as prompt,
                    ):
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
                    with (
                        patch.object(sisctl, "compose") as compose,
                        patch.object(
                            sisctl,
                            "preflight_card_references",
                        ) as preflight,
                        patch.object(sisctl.getpass, "getpass", return_value="test-only") as prompt,
                    ):
                        sisctl.initialize(configuration, options)
                    preflight.assert_called_once_with({"SIS_MODE": variant})
                    prompt.assert_called_once()
                    self.assertEqual(compose.call_count, 5)
                    bootstrap = compose.call_args_list[3]
                    self.assertIn(f"api-{variant}", bootstrap.args)
                    self.assertIn("bootstrap_institution", bootstrap.args)
                    self.assertEqual(bootstrap.kwargs["input"], b"test-only\n")

    def test_prebuilt_initialization_preserves_preflight_and_bootstrap_without_building(self):
        options = self.options("school", "secondaire")
        options.no_build = True
        with (
            patch.object(sisctl, "compose") as compose,
            patch.object(sisctl, "preflight_card_references") as preflight,
            patch.object(sisctl.getpass, "getpass", return_value="test-only"),
        ):
            sisctl.initialize({"SIS_MODE": "secondaire"}, options)
        preflight.assert_called_once_with({"SIS_MODE": "secondaire"})
        self.assertFalse(any(call.args[1] == "build" for call in compose.call_args_list))
        self.assertIn("bootstrap_institution", compose.call_args_list[2].args)


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
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
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
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            options = self.options(directory, [public])
            with patch.object(sisctl.getpass, "getpass", return_value="throwaway-test-only"):
                sisctl.configure(options)
            saved = sisctl.read_configuration(options.env_file)
            self.assertEqual(json.loads(saved["EDX_JWT_PUBLIC_SIGNING_JWK_SET"]), {"keys": [public]})
            self.assertEqual(options.env_file.stat().st_mode & 0o777, 0o600)

    def test_standalone_configuration_and_offline_preflight_need_no_lms_or_secret_prompt(self):
        for local in (True, False):
            with self.subTest(local=local), tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
                options = self.options(directory, [])
                options.auth_mode = "local"
                options.local = local
                options.lms_url = options.cms_url = options.jwks = None
                with patch.object(sisctl.getpass, "getpass", side_effect=AssertionError("Must not prompt")):
                    sisctl.configure(options)
                configuration = sisctl.read_configuration(options.env_file)
                self.assertFalse(any(key.startswith("EDX_") for key in configuration))
                self.assertEqual(configuration["CORS_ALLOWED_ORIGINS"], configuration["FRONTEND_URL"])
                with patch.object(sisctl.subprocess, "run", side_effect=AssertionError("Must remain offline")):
                    sisctl.validate_configuration(configuration)
                with self.assertRaisesRegex(ValueError, "EDX_LMS_URL"):
                    sisctl.validate_configuration({**configuration, "SIS_AUTH_MODE": "lms"})
                with self.assertRaisesRegex(ValueError, "EDX_CMS_URL"):
                    sisctl.validate_configuration({**configuration, "EDX_LMS_URL": "https://lms.example"})

    def test_local_auth_can_configure_provisioning_without_enabling_jwt(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            options = self.options(directory, [])
            options.auth_mode = "local"
            options.jwks = None
            with patch.object(sisctl.getpass, "getpass", return_value="throwaway-test-only"):
                sisctl.configure(options)
            configuration = sisctl.read_configuration(options.env_file)
            sisctl.validate_configuration(configuration)
            self.assertEqual(configuration["EDX_OAUTH_CLIENT_ID"], "sis-test")
            self.assertFalse(any(key.startswith("EDX_JWT_") for key in configuration))

    def test_lms_auth_and_partial_integrations_fail_before_prompting(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            options = self.options(directory, [])
            options.jwks = None
            with patch.object(sisctl.getpass, "getpass", side_effect=AssertionError("Must not prompt")):
                with self.assertRaisesRegex(ValueError, "--jwks"):
                    sisctl.configure(options)
                options.auth_mode = "local"
                options.cms_url = None
                with self.assertRaisesRegex(ValueError, "--cms-url"):
                    sisctl.configure(options)
            self.assertFalse(options.env_file.exists())

    def test_refuses_incomplete_lms_or_insecure_studio_urls_before_prompting(self):
        public = {"kty": "RSA", "n": "AQAB", "e": "AQAB"}
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            for url in (
                "https://",
                "https://lms.school.example/oauth2",
                "https://user@lms.school.example",
                "https://lms school.example",
                "https://lms.\nschool.example",
            ):
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
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            options = self.options(directory, [public])
            options.local = True
            options.lms_url = "http://lms.localhost:59080/"
            options.cms_url = "http://studio.localhost:59080/"
            with patch.object(sisctl.getpass, "getpass", return_value="throwaway-test-only"):
                sisctl.configure(options)
            saved = sisctl.read_configuration(options.env_file)
            self.assertEqual(saved["EDX_LMS_URL"], "http://lms.localhost:59080")
            self.assertEqual(saved["EDX_CMS_URL"], "http://studio.localhost:59080")


class OperationsTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.addCleanup(self.directory.cleanup)
        options = ConfigureSafetyTests().options(self.directory.name, [{"kty": "RSA", "n": "AQAB", "e": "AQAB"}])
        options.local = True
        with patch.object(sisctl.getpass, "getpass", return_value="throwaway-test-only"), patch("builtins.print"):
            sisctl.configure(options)
        self.configuration = sisctl.read_configuration(options.env_file)

    def test_refuses_duplicate_assignments_and_invalid_names(self):
        path = Path(self.directory.name) / "invalid.env"
        for content in ("SIS_MODE=dual\nSIS_MODE=secondaire\n", "2INVALID=value\n"):
            with self.subTest(content=content):
                path.write_text(content)
                with self.assertRaisesRegex(ValueError, "line"):
                    sisctl.read_configuration(path)

    def test_literal_values_match_compose_without_interpolation_or_hash_truncation(self):
        path = Path(self.directory.name) / "literal.env"
        path.write_text(
            "UNQUOTED=before#after # comment\n"
            "SINGLE='before$after\\literal#hash' # comment\n"
            'DOUBLE="plain text" # comment\n'
            "EMPTY= # comment\n"
        )
        values = sisctl.read_configuration(path)
        self.assertEqual(values["UNQUOTED"], "before#after")
        self.assertEqual(values["SINGLE"], "before$after\\literal#hash")
        self.assertEqual(values["DOUBLE"], "plain text")
        self.assertEqual(values["EMPTY"], "")
        for value in ("before$AFTER", '"before$AFTER"', r'"before\nAFTER"', "'closed'garbage", "before'after'"):
            with self.subTest(value=value):
                path.write_text(f"SECRET={value}\n")
                with self.assertRaisesRegex(ValueError, "line 1"):
                    sisctl.read_configuration(path)

    def test_compose_uses_file_project_and_keys_not_shell_overrides(self):
        configuration = {**self.configuration, "COMPOSE_PROJECT_NAME": "isolated-recovery"}
        with (
            patch.dict(
                os.environ,
                {
                    "COMPOSE_PROJECT_NAME": "historic-production",
                    "COMPOSE_PROFILES": "superieur",
                    "SIS_IMAGE": "wrong-image",
                    "DB_PASSWORD_SECONDAIRE": "wrong-key",
                    "SIS_ENV_FILE": "wrong.env",
                },
            ),
            patch.object(sisctl.subprocess, "run") as run,
        ):
            sisctl.compose(configuration, "config", "--quiet", env={"PGPASSWORD": "explicit-restore-password"})
        command = run.call_args.args[0]
        environment = run.call_args.kwargs["env"]
        self.assertEqual(command[command.index("--project-name") + 1], "isolated-recovery")
        self.assertEqual(environment["DB_PASSWORD_SECONDAIRE"], configuration["DB_PASSWORD_SECONDAIRE"])
        self.assertEqual(environment["SIS_ENV_FILE"], configuration["_ENV_FILE"])
        self.assertEqual(environment["PGPASSWORD"], "explicit-restore-password")
        self.assertEqual(environment["COMPOSE_PROFILES"], "")
        self.assertEqual(environment["COMPOSE_PROJECT_NAME"], "isolated-recovery")
        self.assertNotIn("SIS_IMAGE", environment)

    def test_offline_checks_reject_unsafe_configuration_without_printing_secrets(self):
        cases = [
            ("FIELD_ENCRYPTION_KEY", "not-base64", "FIELD_ENCRYPTION_KEY"),
            ("DJANGO_SECRET_KEY", "short-secret", "DJANGO_SECRET_KEY"),
            ("DJANGO_DEBUG", "unknown", "DJANGO_DEBUG"),
            ("SIS_BIND_ADDRESS", "0.0.0.0", "loopback"),
            ("SIS_WORKER_CONCURRENCY", "0", "SIS_WORKER_CONCURRENCY"),
            ("SIS_HTTP_PORT", "70000", "distinct ports"),
            ("SIS_HTTPS_PORT", "08080", "distinct ports"),
            ("SIS_FRONTEND_ADDRESS", "http://wrong.example", "match"),
            ("DJANGO_ALLOWED_HOSTS", "*", "explicit API"),
            ("COMPOSE_PROJECT_NAME", "Wrong/Project", "COMPOSE_PROJECT_NAME"),
            ("EDX_OAUTH_CLIENT_SECRET", "$OTHER_KEY", "literal"),
        ]
        for key, value, message in cases:
            with (
                self.subTest(key=key),
                patch("builtins.print") as output,
                patch.object(sisctl.subprocess, "run") as run,
            ):
                with self.assertRaisesRegex(ValueError, message):
                    sisctl.validate_configuration({**self.configuration, key: value})
                run.assert_not_called()
                self.assertNotIn(self.configuration["DJANGO_SECRET_KEY"], str(output.call_args_list))

    def test_environment_file_permissions_are_checked(self):
        path = Path(self.configuration["_ENV_FILE"])
        path.chmod(0o644)
        with self.assertRaisesRegex(ValueError, "0600"):
            sisctl.validate_configuration(self.configuration)

    def test_existing_django_boolean_and_scoped_host_forms_remain_usable(self):
        configuration = {**self.configuration, "DJANGO_DEBUG": "1", "DJANGO_ALLOWED_HOSTS": ".school.example"}
        with patch("builtins.print"):
            sisctl.validate_configuration(configuration)
        with self.assertRaisesRegex(ValueError, "loopback"):
            sisctl.validate_configuration({**configuration, "SIS_BIND_ADDRESS": "0.0.0.0"})

    def test_production_requires_https_even_with_local_auth(self):
        configuration = {**self.configuration, "DJANGO_DEBUG": "False", "SIS_AUTH_MODE": "local"}
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            sisctl.validate_configuration(configuration)

    def test_operation_lock_prevents_overlapping_maintenance_and_releases_after_failure(self):
        with self.assertRaisesRegex(RuntimeError, "simulated"):
            with sisctl.operation_lock(self.configuration):
                with self.assertRaisesRegex(ValueError, "Another SIS maintenance"):
                    with sisctl.operation_lock(self.configuration):
                        self.fail("Overlapping maintenance acquired a lock")
                raise RuntimeError("simulated failure")
        with sisctl.operation_lock(self.configuration):
            pass

    def test_installation_preflight_uses_read_only_commands_and_detects_occupied_port(self):
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            self.configuration["SIS_HTTP_PORT"] = str(listener.getsockname()[1])
            with (
                patch.object(sisctl.subprocess, "run", return_value=SimpleNamespace(stdout="2.30.0\n")) as run,
                patch.object(sisctl, "compose") as compose,
            ):
                with self.assertRaisesRegex(ValueError, "without stopping another service"):
                    sisctl.installation_preflight(self.configuration, check_ports=True)
            self.assertEqual(
                [call.args[0] for call in run.call_args_list],
                [
                    ["docker", "compose", "version", "--short"],
                    ["docker", "info"],
                ],
            )
            self.assertEqual(compose.call_args.args[1:], ("config", "--quiet"))

    def test_old_compose_and_unreachable_daemon_are_blocking(self):
        with patch.object(sisctl.subprocess, "run", return_value=SimpleNamespace(stdout="2.10.0")):
            with self.assertRaisesRegex(ValueError, "Compose >= 2.20"):
                sisctl.installation_preflight(self.configuration)
        with patch.object(sisctl.subprocess, "run", side_effect=FileNotFoundError("docker")):
            with self.assertRaisesRegex(ValueError, "No container was started"):
                sisctl.installation_preflight(self.configuration)

    def runtime_records(self):
        return [
            {"Service": service, "State": "running", "Health": "" if service.startswith("beat-") else "healthy"}
            for service in ["redis", "frontend", "gateway"]
            + [
                f"{role}-{variant}"
                for variant in ("secondaire", "superieur")
                for role in ("postgres", "api", "worker", "beat")
            ]
        ]

    def test_status_accepts_compose_array_and_line_delimited_json(self):
        expected = self.runtime_records()
        for text in (json.dumps(expected), "\n".join(json.dumps(record) for record in expected)):
            with patch.object(sisctl, "compose", return_value=SimpleNamespace(stdout=text)):
                self.assertEqual(sisctl.service_status(self.configuration), expected)

    def test_doctor_checks_both_workers_and_duplicate_beat_without_executing_tasks(self):
        configuration = {**self.configuration, "SIS_MODE": "dual"}
        records = self.runtime_records()
        with (
            patch.object(sisctl, "installation_preflight"),
            patch.object(
                sisctl,
                "service_status",
                return_value=records,
            ),
            patch("builtins.print") as output,
        ):
            sisctl.doctor(configuration)
            next(record for record in records if record["Service"] == "worker-superieur")["Health"] = "unhealthy"
            records.append({"Service": "beat-secondaire", "State": "running", "Health": ""})
            with self.assertRaisesRegex(ValueError, "Runtime diagnosis failed"):
                sisctl.doctor(configuration)
        self.assertIn("FAIL worker-superieur", str(output.call_args_list))
        self.assertIn("multiple schedulers", str(output.call_args_list))

    def test_update_requires_backup_attestation_before_any_effect(self):
        with patch.object(sisctl, "compose") as compose, patch.object(sisctl, "installation_preflight") as preflight:
            with self.assertRaisesRegex(ValueError, "--confirm-backup"):
                sisctl.update(self.configuration, SimpleNamespace(confirm_backup=False))
            compose.assert_not_called()
            preflight.assert_not_called()

    def test_update_migrates_all_tenants_without_bootstrap_or_password_prompt(self):
        configuration = {**self.configuration, "SIS_MODE": "dual"}
        calls = []
        with (
            patch.object(sisctl, "installation_preflight"),
            patch.object(
                sisctl,
                "service_status",
                return_value=self.runtime_records(),
            ),
            patch.object(
                sisctl,
                "compose",
                side_effect=lambda _configuration, *args: calls.append(args),
            ),
            patch.object(
                sisctl,
                "preflight_card_references",
                side_effect=lambda _configuration: calls.append(("preflight",)),
            ),
            patch.object(sisctl, "doctor") as doctor,
            patch.object(sisctl.getpass, "getpass") as prompt,
        ):
            sisctl.update(configuration, SimpleNamespace(confirm_backup=True))
        self.assertEqual([call[0] for call in calls[:4]], ["build", "build", "stop", "preflight"])
        self.assertEqual(calls[:2], [("build", "api-secondaire"), ("build", "frontend")])
        for variant in ("secondaire", "superieur"):
            migrations = [call for call in calls if f"api-{variant}" in call and "migrate_schemas" in call]
            self.assertEqual([call[-2] for call in migrations], ["--shared", "--tenant"])
        self.assertFalse(any("bootstrap_institution" in call for call in calls))
        self.assertEqual(calls[-1], ("up", "-d", "--no-build", "--wait"))
        prompt.assert_not_called()
        doctor.assert_called_once_with(configuration)

    def test_failed_migration_leaves_writers_stopped_and_never_restarts_old_code(self):
        calls = []

        def fake_compose(_configuration, *args):
            calls.append(args)
            if "migrate_schemas" in args:
                raise subprocess.CalledProcessError(1, ["migration"])

        with (
            patch.object(sisctl, "installation_preflight"),
            patch.object(
                sisctl,
                "service_status",
                return_value=self.runtime_records(),
            ),
            patch.object(sisctl, "compose", side_effect=fake_compose),
            patch.object(
                sisctl,
                "preflight_card_references",
            ),
            patch.object(sisctl, "doctor") as doctor,
        ):
            with self.assertRaisesRegex(ValueError, "remain stopped"):
                sisctl.update(self.configuration, SimpleNamespace(confirm_backup=True))
        self.assertTrue(any(call[0] == "stop" for call in calls))
        self.assertFalse(any(call[0] == "up" for call in calls))
        doctor.assert_not_called()

    def test_update_can_use_prepared_release_images_without_rebuilding(self):
        with (
            patch.object(sisctl, "installation_preflight"),
            patch.object(
                sisctl,
                "service_status",
                return_value=self.runtime_records(),
            ),
            patch.object(sisctl, "compose") as compose,
            patch.object(
                sisctl,
                "preflight_card_references",
            ),
            patch.object(sisctl, "doctor"),
        ):
            sisctl.update(self.configuration, SimpleNamespace(confirm_backup=True, no_build=True))
        self.assertFalse(any(call.args[1] == "build" for call in compose.call_args_list))


if __name__ == "__main__":
    unittest.main()
