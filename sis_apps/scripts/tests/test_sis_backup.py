import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts import sis_backup


class RestorePreflightTests(unittest.TestCase):
    def restore(
        self, existing_volume=None, existing_entry="empty-directory", snapshot_selector="test-snapshot",
        manifest_format=1, fail_import=False,
    ):
        configuration = {
            "SIS_MODE": "secondaire",
            "COMPOSE_PROJECT_NAME": "restored-project",
            "FIELD_ENCRYPTION_KEY": "test-key",
            "DJANGO_SECRET_KEY": "test-django-key",
            "WEBHOOK_SECRET": "test-webhook-key",
            "DB_PASSWORD_SECONDAIRE": "test-password",
        }
        options = SimpleNamespace(snapshot=snapshot_selector, confirm_empty_target=True)
        volumes = {"data-secondaire": "test-data", "redis": "test-redis"}
        manifest = {
            "format": manifest_format,
            "variants": ["secondaire"],
            "postgres_major": 16,
            "field_key_sha256": hashlib.sha256(b"test-key").hexdigest(),
            "project": "source-project",
            "secret_sha256": {
                key: hashlib.sha256(configuration[key].encode()).hexdigest()
                for key in ("DJANGO_SECRET_KEY", "FIELD_ENCRYPTION_KEY", "WEBHOOK_SECRET")
            },
        }
        compose_calls = []
        restic_calls = []
        volume_checks = []

        def fake_compose(_configuration, *arguments, **_kwargs):
            compose_calls.append(arguments)
            if arguments[:2] == ("ps", "--services"):
                return SimpleNamespace(stdout=b"")
            if arguments[:2] == ("exec", "-T"):
                return SimpleNamespace(stdout=b"0\n")
            if arguments[0] == "run" and fail_import:
                raise subprocess.CalledProcessError(1, ["pg_restore"])
            return SimpleNamespace()

        def fake_restic(_options, *arguments, **_kwargs):
            restic_calls.append(arguments)
            if arguments[0] == "snapshots":
                return SimpleNamespace(stdout=json.dumps([{"id": "a" * 64}]).encode())
            if arguments[0] == "dump":
                return SimpleNamespace(stdout=json.dumps(manifest).encode())
            return SimpleNamespace()

        def fake_run(command, **_kwargs):
            if "find /target" in command[-1]:
                volume_checks.append(command[-1])
                volume = next(arg for arg in command if arg.startswith("type=volume,source=")).split(",")[1]
                name = volume.removeprefix("source=")
                # Directories and symlinks are invisible to the old `find -type f` check.
                output = (
                    f"/target/{existing_entry}\n".encode()
                    if name == existing_volume and "-mindepth 1" in command[-1]
                    else b""
                )
                return SimpleNamespace(stdout=output)
            return SimpleNamespace()

        with patch.object(sis_backup, "compose", side_effect=fake_compose), patch.object(
            sis_backup, "restic", side_effect=fake_restic
        ), patch.object(sis_backup, "volume_names", return_value=volumes), patch.object(
            sis_backup.subprocess, "run", side_effect=fake_run
        ):
            if existing_volume:
                with self.assertRaisesRegex(ValueError, "Volume test-data is not empty"):
                    sis_backup.restore(options, configuration)
            elif fail_import:
                with self.assertRaisesRegex(ValueError, "partially restored"):
                    sis_backup.restore(options, configuration)
            else:
                sis_backup.restore(options, configuration)
        return compose_calls, restic_calls, volume_checks

    def test_refuses_volume_with_empty_directory_before_restoring(self):
        compose_calls, restic_calls, volume_checks = self.restore(existing_volume="test-data")
        self.assertEqual(len(volume_checks), 1)
        self.assertFalse(any(call[0] == "restore" for call in restic_calls))
        self.assertFalse(any(call[0] == "run" for call in compose_calls))

    def test_refuses_volume_with_symlink_before_restoring(self):
        _, restic_calls, _ = self.restore(existing_volume="test-data", existing_entry="dangling-symlink")
        self.assertFalse(any(call[0] == "restore" for call in restic_calls))

    def test_restores_when_all_target_volumes_are_empty(self):
        compose_calls, restic_calls, volume_checks = self.restore()
        self.assertEqual(len(volume_checks), 2)
        self.assertTrue(all("-mindepth 1" in check for check in volume_checks))
        self.assertEqual(len([call for call in restic_calls if call[0] == "restore"]), 1)
        self.assertEqual(len([call for call in compose_calls if call[0] == "run"]), 1)

    def test_pins_latest_for_manifest_validation_and_restore(self):
        _, restic_calls, _ = self.restore(snapshot_selector="latest")
        self.assertEqual(restic_calls[0], ("snapshots", "--json", "latest"))
        self.assertEqual(
            [call[1] for call in restic_calls if call[0] in ("dump", "restore")],
            ["a" * 64, "a" * 64],
        )

    def test_new_snapshot_format_restores_into_different_project_with_original_keys(self):
        compose_calls, restic_calls, _ = self.restore(manifest_format=2)
        self.assertEqual(len([call for call in compose_calls if call[0] == "run"]), 1)
        self.assertEqual(len([call for call in restic_calls if call[0] == "restore"]), 1)

    def test_partial_restore_error_does_not_start_applications(self):
        compose_calls, _, _ = self.restore(manifest_format=2, fail_import=True)
        self.assertEqual(
            [call for call in compose_calls if call[0] == "up"],
            [("up", "-d", "--wait", "postgres-secondaire")],
        )

    def test_refuses_unresolved_snapshot_before_touching_target(self):
        options = SimpleNamespace(snapshot="latest", confirm_empty_target=True)
        configuration = {"SIS_MODE": "secondaire", "FIELD_ENCRYPTION_KEY": "test-key"}
        invalid_results = [
            [],
            [{"id": "a" * 64}, {"id": "b" * 64}],
            [{"id": "a" * 8}],
            [{"id": "latest"}],
            [{}],
            {},
        ]
        for result in invalid_results:
            with self.subTest(result=result), patch.object(
                sis_backup, "restic", return_value=SimpleNamespace(stdout=json.dumps(result).encode())
            ) as restic, patch.object(sis_backup, "compose") as compose, patch.object(
                sis_backup.subprocess, "run"
            ) as run:
                with self.assertRaisesRegex(ValueError, "exactly one full snapshot ID"):
                    sis_backup.restore(options, configuration)
                restic.assert_called_once_with(options, "snapshots", "--json", "latest", capture_output=True)
                compose.assert_not_called()
                run.assert_not_called()


class SnapshotReliabilityTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name).resolve()
        self.repository = self.root / "repository"
        self.repository.mkdir()
        (self.repository / "config").touch()
        self.configuration = {
            "SIS_MODE": "secondaire", "COMPOSE_PROJECT_NAME": "test-source",
            "FIELD_ENCRYPTION_KEY": "test-field-key", "DJANGO_SECRET_KEY": "test-django-key",
            "WEBHOOK_SECRET": "test-webhook-key", "_ENV_FILE": str(self.root / ".env"),
        }
        self.options = SimpleNamespace(repository=self.repository, staging_dir=None)
        self.volumes = {"redis": "test-redis", "data-secondaire": "test-data"}
        self.calls = []
        self.manifest = None

    def compose(self, _configuration, *arguments, **kwargs):
        self.calls.append(arguments)
        if arguments[0] == "ps":
            # Beat was deliberately stopped before the backup.
            return SimpleNamespace(stdout=b"postgres-secondaire\nredis\napi-secondaire\nworker-secondaire\n")
        if arguments[0] == "images":
            return SimpleNamespace(stdout=b'[{"ID": "sha256:example", "Service": "api-secondaire"}]')
        if "pg_dump" in arguments:
            kwargs["stdout"].write(b"synthetic database dump")
        return SimpleNamespace()

    def restic(self, _options, *arguments, **kwargs):
        if arguments[0] == "backup":
            source = kwargs["mounts"][0].split(",source=")[1].split(",target=")[0]
            staging = Path(source)
            self.assertEqual(staging.parent, self.root)
            self.assertEqual(staging.stat().st_mode & 0o777, 0o700)
            self.assertEqual((staging / "secondaire.dump").read_bytes(), b"synthetic database dump")
            self.manifest = json.loads((staging / "manifest.json").read_text())
            self.assertIn("project:test-source", arguments)
        return SimpleNamespace()

    def test_snapshot_records_images_and_keys_and_restarts_only_original_writers(self):
        with patch.object(sis_backup, "volume_names", return_value=self.volumes), patch.object(
            sis_backup, "compose", side_effect=self.compose,
        ), patch.object(sis_backup, "restic", side_effect=self.restic), patch.object(
            sis_backup.subprocess, "run",
        ) as run:
            sis_backup.snapshot(self.options, self.configuration)
        self.assertEqual([call.args[0][:3] for call in run.call_args_list], [
            ["docker", "volume", "inspect"], ["docker", "volume", "inspect"],
        ])
        self.assertEqual(self.manifest["format"], 2)
        self.assertEqual(self.manifest["project"], "test-source")
        self.assertEqual(self.manifest["images"][0]["ID"], "sha256:example")
        self.assertNotIn("test-field-key", json.dumps(self.manifest))
        restart = self.calls[-1]
        self.assertEqual(restart[:6], ("up", "-d", "--no-build", "--no-deps", "--wait", "api-secondaire"))
        self.assertNotIn("beat-secondaire", restart)
        self.assertFalse(list(self.root.glob(".sis-snapshot-*")))

    def test_missing_data_volume_aborts_before_stopping_or_creating_empty_backup(self):
        with patch.object(sis_backup, "volume_names", return_value=self.volumes), patch.object(
            sis_backup, "compose", side_effect=self.compose,
        ), patch.object(sis_backup, "restic") as restic, patch.object(
            sis_backup.subprocess, "run", side_effect=subprocess.CalledProcessError(1, ["volume", "inspect"]),
        ):
            with self.assertRaisesRegex(ValueError, "misleading empty backup"):
                sis_backup.snapshot(self.options, self.configuration)
        self.assertFalse(any(call[0] == "stop" for call in self.calls))
        restic.assert_not_called()

    def test_plaintext_staging_cannot_be_placed_inside_encrypted_repository(self):
        self.options.staging_dir = self.repository
        with patch.object(sis_backup, "volume_names", return_value=self.volumes), patch.object(
            sis_backup, "compose", side_effect=self.compose,
        ), patch.object(sis_backup, "restic") as restic, patch.object(sis_backup.subprocess, "run"):
            with self.assertRaisesRegex(ValueError, "plaintext staging outside"):
                sis_backup.snapshot(self.options, self.configuration)
        self.assertFalse(any(call[0] == "stop" for call in self.calls))
        restic.assert_not_called()

    def test_failed_dump_restarts_writers_and_removes_plaintext_staging(self):
        def failing_dump(configuration, *arguments, **kwargs):
            result = self.compose(configuration, *arguments, **kwargs)
            if arguments[0] == "exec":
                raise subprocess.CalledProcessError(1, ["pg_dump"])
            return result

        with patch.object(sis_backup, "volume_names", return_value=self.volumes), patch.object(
            sis_backup, "compose", side_effect=failing_dump,
        ), patch.object(sis_backup, "restic") as restic, patch.object(sis_backup.subprocess, "run"):
            with self.assertRaises(subprocess.CalledProcessError):
                sis_backup.snapshot(self.options, self.configuration)
        self.assertEqual(self.calls[-1][0], "up")
        self.assertIn("--no-deps", self.calls[-1])
        self.assertFalse(list(self.root.glob(".sis-snapshot-*")))
        restic.assert_not_called()

    def test_restore_refuses_source_project_and_changed_authentication_keys_before_docker(self):
        manifest = {
            "format": 2, "postgres_major": 16, "variants": ["secondaire"], "project": "test-source",
            "field_key_sha256": hashlib.sha256(b"test-field-key").hexdigest(),
            "secret_sha256": {
                key: hashlib.sha256(self.configuration[key].encode()).hexdigest()
                for key in ("DJANGO_SECRET_KEY", "FIELD_ENCRYPTION_KEY", "WEBHOOK_SECRET")
            },
        }
        options = SimpleNamespace(snapshot="a" * 64, confirm_empty_target=True)
        for changes, error in (
            ({}, "different COMPOSE_PROJECT_NAME"),
            ({"COMPOSE_PROJECT_NAME": "test-restored", "DJANGO_SECRET_KEY": "different"}, "DJANGO_SECRET_KEY"),
            ({"COMPOSE_PROJECT_NAME": "test-restored", "WEBHOOK_SECRET": "different"}, "WEBHOOK_SECRET"),
        ):
            with self.subTest(changes=changes), patch.object(
                sis_backup, "resolve_snapshot", return_value="a" * 64,
            ), patch.object(
                sis_backup, "restic", return_value=SimpleNamespace(stdout=json.dumps(manifest).encode()),
            ), patch.object(sis_backup, "compose") as compose, patch.object(sis_backup.subprocess, "run") as run:
                with self.assertRaisesRegex(ValueError, error):
                    sis_backup.restore(options, {**self.configuration, **changes})
                compose.assert_not_called()
                run.assert_not_called()

    def test_missing_repository_check_fails_without_creating_a_directory(self):
        password = self.root / "password"
        password.write_text("test-only-password")
        password.chmod(0o600)
        missing = self.root / "missing-repository"
        with patch("sys.argv", [
            "sis_backup.py", "--repository", str(missing), "--password-file", str(password), "check",
        ]), patch.object(sis_backup, "restic") as restic, patch("sys.stderr"):
            with self.assertRaises(SystemExit) as error:
                sis_backup.main()
        self.assertEqual(error.exception.code, 1)
        self.assertFalse(missing.exists())
        restic.assert_not_called()

    def test_missing_required_mount_fails_before_initializing_repository(self):
        password = self.root / "password"
        password.write_text("test-only-password")
        password.chmod(0o600)
        with patch("sys.argv", [
            "sis_backup.py", "--repository", str(self.repository), "--password-file", str(password),
            "--require-mount", str(self.root), "backup",
        ]), patch.object(sis_backup, "restic") as restic, patch("sys.stderr"):
            with self.assertRaises(SystemExit) as error:
                sis_backup.main()
        self.assertEqual(error.exception.code, 1)
        restic.assert_not_called()

    def test_inspect_excludes_key_fingerprints_and_configuration(self):
        password = self.root / "password"
        password.write_text("test-only-password")
        password.chmod(0o600)
        manifest = {
            "format": 2, "project": "source", "images": [{"ID": "sha256:example"}],
            "field_key_sha256": "private-fingerprint", "secret_sha256": {"key": "private-fingerprint"},
            "configuration": "must-not-be-printed",
        }
        with patch("sys.argv", [
            "sis_backup.py", "--repository", str(self.repository), "--password-file", str(password),
            "inspect", "--snapshot", "latest",
        ]), patch.object(sis_backup, "resolve_snapshot", return_value="a" * 64), patch.object(
            sis_backup, "restic", return_value=SimpleNamespace(stdout=json.dumps(manifest).encode()),
        ), patch("builtins.print") as output:
            sis_backup.main()
        printed = output.call_args.args[0]
        self.assertIn("sha256:example", printed)
        self.assertIn("a" * 64, printed)
        self.assertNotIn("private-fingerprint", printed)
        self.assertNotIn("must-not-be-printed", printed)


if __name__ == "__main__":
    unittest.main()
