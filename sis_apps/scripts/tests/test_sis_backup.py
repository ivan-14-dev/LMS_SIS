import hashlib
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from scripts import sis_backup


class RestorePreflightTests(unittest.TestCase):
    def restore(self, existing_volume=None, existing_entry="empty-directory"):
        configuration = {
            "SIS_MODE": "secondaire",
            "FIELD_ENCRYPTION_KEY": "test-key",
            "DB_PASSWORD_SECONDAIRE": "test-password",
        }
        options = SimpleNamespace(snapshot="test-snapshot", confirm_empty_target=True)
        volumes = {"data-secondaire": "test-data", "redis": "test-redis"}
        manifest = {
            "format": 1,
            "variants": ["secondaire"],
            "postgres_major": 16,
            "field_key_sha256": hashlib.sha256(b"test-key").hexdigest(),
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
            return SimpleNamespace()

        def fake_restic(_options, *arguments, **_kwargs):
            restic_calls.append(arguments)
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


if __name__ == "__main__":
    unittest.main()
