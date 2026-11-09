#!/usr/bin/env python3
"""Encrypted, local-only SIS snapshots and restoration pinned to one snapshot in an empty deployment."""

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path

if __package__:
    from .sisctl import (
        ROOT,
        compose,
        operation_lock,
        project_name,
        read_configuration,
        validate_configuration,
        variants,
    )
else:
    from sisctl import ROOT, compose, operation_lock, project_name, read_configuration, validate_configuration, variants

RESTIC_IMAGE = "restic/restic:0.18.1"


def restic(options, *arguments, mounts=(), **kwargs):
    command = [
        "docker",
        "run",
        "--rm",
        "--network",
        "none",
        "--security-opt",
        "no-new-privileges:true",
        "--mount",
        f"type=bind,source={options.repository},target=/repository",
        "--mount",
        f"type=bind,source={options.password_file},target=/run/password,readonly",
    ]
    for mount in mounts:
        command.extend(["--mount", mount])
    return subprocess.run(
        [
            *command,
            RESTIC_IMAGE,
            "--no-cache",
            "-r",
            "/repository",
            "-p",
            "/run/password",
            *arguments,
        ],
        check=True,
        **kwargs,
    )


def volume_names(configuration):
    definition = json.loads(compose(configuration, "config", "--format", "json", capture_output=True).stdout)
    return {key: value["name"] for key, value in definition["volumes"].items()}


def database_arguments(configuration, variant):
    return [
        "-U",
        configuration.get("DB_USER", "sis"),
        "-d",
        configuration.get(f"DB_NAME_{variant.upper()}", f"sis_{variant}"),
    ]


def snapshot(options, configuration):
    selected = variants(configuration)
    volumes = volume_names(configuration)
    running = (
        compose(
            configuration,
            "ps",
            "--services",
            "--status",
            "running",
            capture_output=True,
        )
        .stdout.decode()
        .split()
    )
    writers = [service for service in running if service == "redis" or service.startswith(("api-", "worker-", "beat-"))]
    if not all(f"postgres-{variant}" in running for variant in selected):
        raise ValueError("Start the selected databases before creating a snapshot.")
    for key in ["redis", *[f"data-{variant}" for variant in selected]]:
        try:
            subprocess.run(
                ["docker", "volume", "inspect", volumes[key]],
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError as exc:
            raise ValueError(
                f"Required volume {key} is missing; refusing to create a misleading empty backup."
            ) from exc
    images = json.loads(compose(configuration, "images", "--format", "json", capture_output=True).stdout)
    if not isinstance(images, list) or not images:
        raise ValueError("Cannot record deployed image IDs; refusing a snapshot without its runtime inventory.")
    staging_directory = (getattr(options, "staging_dir", None) or Path(configuration["_ENV_FILE"]).parent).resolve(
        strict=True
    )
    if not staging_directory.is_dir():
        raise ValueError("The private staging directory must already exist and have room for the database dumps.")
    if staging_directory.is_relative_to(options.repository):
        raise ValueError("Keep plaintext staging outside the encrypted backup repository.")
    if not (options.repository / "config").exists():
        restic(options, "init")
    stopped = []
    try:
        application_services = [service for service in writers if service != "redis"]
        if application_services:
            stopped.extend(application_services)
            compose(configuration, "stop", "--timeout", "120", *application_services)
        if "redis" in writers:
            stopped.append("redis")
            compose(configuration, "stop", "redis")
        with tempfile.TemporaryDirectory(prefix=".sis-snapshot-", dir=staging_directory) as temporary:
            staging = Path(temporary)
            for variant in selected:
                dump = staging / f"{variant}.dump"
                with dump.open("wb") as output:
                    compose(
                        configuration,
                        "exec",
                        "-T",
                        f"postgres-{variant}",
                        "pg_dump",
                        "--format=custom",
                        *database_arguments(configuration, variant),
                        stdout=output,
                    )
                with dump.open("rb") as source:
                    compose(
                        configuration,
                        "exec",
                        "-T",
                        f"postgres-{variant}",
                        "pg_restore",
                        "--list",
                        stdin=source,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.PIPE,
                    )
            manifest = {
                "format": 2,
                "variants": selected,
                "postgres_major": 16,
                "field_key_sha256": hashlib.sha256(configuration["FIELD_ENCRYPTION_KEY"].encode()).hexdigest(),
                "secret_sha256": {
                    key: hashlib.sha256(configuration[key].encode()).hexdigest()
                    for key in ("DJANGO_SECRET_KEY", "FIELD_ENCRYPTION_KEY", "WEBHOOK_SECRET")
                },
                "project": project_name(configuration),
                "created_at": datetime.now(UTC).isoformat(),
                "images": images,
            }
            (staging / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            mounts = [
                f"type=bind,source={staging},target=/snapshot/database,readonly",
                f"type=bind,source={configuration['_ENV_FILE']},target=/snapshot/configuration/.env,readonly",
                f"type=volume,source={volumes['redis']},target=/snapshot/redis,readonly",
                *[
                    f"type=volume,source={volumes[f'data-{variant}']},target=/snapshot/data/{variant},readonly"
                    for variant in selected
                ],
            ]
            restic(
                options,
                "backup",
                "--host",
                "lms-sis",
                "--tag",
                "sis-v1",
                "--tag",
                f"project:{project_name(configuration)}",
                "/snapshot",
                mounts=mounts,
            )
    finally:
        if stopped:
            compose(configuration, "up", "-d", "--no-build", "--no-deps", "--wait", *stopped)
    restic(options, "check")


def resolve_snapshot(options):
    """Resolve mutable selectors once for configuration, manifest and data reads."""
    snapshots = json.loads(restic(options, "snapshots", "--json", options.snapshot, capture_output=True).stdout)
    snapshot_id = (
        snapshots[0].get("id")
        if isinstance(snapshots, list) and len(snapshots) == 1 and isinstance(snapshots[0], dict)
        else None
    )
    if (
        not isinstance(snapshot_id, str)
        or len(snapshot_id) != 64
        or any(character not in "0123456789abcdef" for character in snapshot_id)
    ):
        raise ValueError("Restore requires exactly one full snapshot ID from the snapshot lookup.")
    return snapshot_id


def restore(options, configuration):
    if not options.confirm_empty_target:
        raise ValueError("Restore requires --confirm-empty-target and a fresh deployment, never a live database.")
    selected = variants(configuration)
    snapshot_id = resolve_snapshot(options)
    manifest = json.loads(
        restic(
            options,
            "dump",
            snapshot_id,
            "/snapshot/database/manifest.json",
            capture_output=True,
        ).stdout
    )
    if (
        not isinstance(manifest, dict)
        or manifest.get("format") not in (1, 2)
        or manifest.get("postgres_major") != 16
        or manifest.get("variants") != selected
    ):
        raise ValueError("Snapshot format, database version or SIS_MODE differs from this deployment.")
    if manifest["format"] == 2:
        if manifest.get("project") == project_name(configuration):
            raise ValueError("Use a different COMPOSE_PROJECT_NAME from the source snapshot for isolated restoration.")
        expected = manifest.get("secret_sha256")
        if not isinstance(expected, dict):
            raise ValueError("Snapshot authentication key fingerprints are missing or invalid.")
        for key in ("DJANGO_SECRET_KEY", "FIELD_ENCRYPTION_KEY", "WEBHOOK_SECRET"):
            if expected.get(key) != hashlib.sha256(configuration.get(key, "").encode()).hexdigest():
                raise ValueError(f"Restore the original {key} before restoring authentication/encrypted data.")
    fingerprint = hashlib.sha256(configuration["FIELD_ENCRYPTION_KEY"].encode()).hexdigest()
    if manifest["field_key_sha256"] != fingerprint:
        raise ValueError("Restore the original .env encryption key before restoring encrypted institution records.")
    running = (
        compose(
            configuration,
            "ps",
            "--services",
            "--status",
            "running",
            capture_output=True,
        )
        .stdout.decode()
        .split()
    )
    if any(service == "redis" or service.startswith(("api-", "worker-", "beat-")) for service in running):
        raise ValueError("Stop the application and Redis before restoring.")
    compose(
        configuration,
        "up",
        "-d",
        "--wait",
        *[f"postgres-{variant}" for variant in selected],
    )
    for variant in selected:
        result = compose(
            configuration,
            "exec",
            "-T",
            f"postgres-{variant}",
            "psql",
            *database_arguments(configuration, variant),
            "-tAc",
            "SELECT count(*) FROM pg_tables WHERE schemaname NOT IN ('pg_catalog','information_schema')",
            capture_output=True,
        )
        if result.stdout.strip() != b"0":
            raise ValueError(f"The {variant} database is not empty. Restore into a separate, fresh deployment.")
    volumes = volume_names(configuration)
    data_volumes = [volumes[f"data-{variant}"] for variant in selected] + [volumes["redis"]]
    for name in data_volumes:
        subprocess.run(["docker", "volume", "create", name], check=True, stdout=subprocess.DEVNULL)
        result = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "--network",
                "none",
                "--entrypoint",
                "sh",
                "--mount",
                f"type=volume,source={name},target=/target,readonly",
                RESTIC_IMAGE,
                "-c",
                "find /target -mindepth 1 -print -quit",
            ],
            check=True,
            capture_output=True,
        )
        if result.stdout.strip():
            raise ValueError(f"Volume {name} is not empty. No files were overwritten.")
    staging = f"sis-restore-{uuid.uuid4().hex}"
    subprocess.run(["docker", "volume", "create", staging], check=True, stdout=subprocess.DEVNULL)
    try:
        mounts = [
            f"type=volume,source={staging},target=/restore",
            f"type=volume,source={volumes['redis']},target=/restore/snapshot/redis",
            *[
                f"type=volume,source={volumes[f'data-{variant}']},target=/restore/snapshot/data/{variant}"
                for variant in selected
            ],
        ]
        restic(
            options,
            "restore",
            snapshot_id,
            "--target",
            "/restore",
            "--verify",
            mounts=mounts,
        )
        for variant in selected:
            compose(
                configuration,
                "run",
                "--rm",
                "--no-deps",
                "-T",
                "-v",
                f"{staging}:/restore:ro",
                "-e",
                "PGPASSWORD",
                f"postgres-{variant}",
                "pg_restore",
                "--exit-on-error",
                "--single-transaction",
                "--no-owner",
                "-h",
                f"postgres-{variant}",
                *database_arguments(configuration, variant),
                f"/restore/snapshot/database/{variant}.dump",
                env={"PGPASSWORD": configuration[f"DB_PASSWORD_{variant.upper()}"]},
            )
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        raise ValueError(
            "Restore failed; target databases/volumes may be partially restored. No application was started. "
            "Keep the source untouched and retry into a new empty project, not over this partial target."
        ) from exc
    finally:
        subprocess.run(["docker", "volume", "rm", staging], check=True, stdout=subprocess.DEVNULL)
    print(f"Snapshot {snapshot_id} restored. Verify domains, image inventory and queued tasks before starting.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repository",
        type=Path,
        required=True,
        help="Local encrypted repository; no network uploads.",
    )
    parser.add_argument("--password-file", type=Path, required=True)
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    parser.add_argument(
        "--staging-dir",
        type=Path,
        help="Existing private directory for database dumps (default: environment file directory, never /tmp).",
    )
    parser.add_argument(
        "--require-mount",
        type=Path,
        help="Refuse operations unless this repository ancestor is a mounted filesystem.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("backup")
    commands.add_parser("snapshots")
    commands.add_parser("check", help="Read and verify all encrypted snapshot data.")
    commands.add_parser(
        "prune",
        help="Keep 7 daily, 4 weekly and 12 monthly snapshots; remove older snapshots.",
    )
    recover = commands.add_parser("restore")
    recover.add_argument("--snapshot", required=True)
    recover.add_argument("--confirm-empty-target", action="store_true")
    recover_config = commands.add_parser("recover-config")
    recover_config.add_argument("--snapshot", required=True)
    recover_config.add_argument("--output", type=Path, required=True)
    inventory = commands.add_parser(
        "inspect", help="Show the snapshot's image inventory, never its configuration/secrets."
    )
    inventory.add_argument("--snapshot", required=True)
    options = parser.parse_args()
    try:
        options.repository = options.repository.resolve()
        options.password_file = options.password_file.resolve(strict=True)
        if not options.password_file.is_file() or options.password_file.stat().st_mode & 0o077:
            raise ValueError("The backup password file must be a regular file with permissions 0600 (or stricter).")
        if not options.password_file.read_text().strip():
            raise ValueError("The backup password file must not be empty.")
        if options.repository == options.password_file or options.repository in options.password_file.parents:
            raise ValueError("Keep the password file outside the encrypted backup repository.")
        if options.require_mount:
            mount = options.require_mount.resolve(strict=True)
            if not mount.is_mount() or not options.repository.is_relative_to(mount):
                raise ValueError("--require-mount must be a mounted filesystem containing the backup repository.")
        if options.command == "backup":
            options.repository.mkdir(mode=0o700, parents=True, exist_ok=True)
        elif not (options.repository / "config").is_file():
            raise ValueError("The Restic repository is missing; check the path/mount before recovery or verification.")
        if options.command == "inspect":
            snapshot_id = resolve_snapshot(options)
            manifest = json.loads(
                restic(options, "dump", snapshot_id, "/snapshot/database/manifest.json", capture_output=True).stdout
            )
            if not isinstance(manifest, dict):
                raise ValueError("Invalid snapshot manifest.")
            print(
                json.dumps(
                    {
                        "snapshot": snapshot_id,
                        **{key: manifest.get(key) for key in ("format", "project", "created_at", "variants", "images")},
                    },
                    indent=2,
                )
            )
        elif options.command == "recover-config":
            snapshot_id = resolve_snapshot(options)
            data = restic(
                options,
                "dump",
                snapshot_id,
                "/snapshot/configuration/.env",
                capture_output=True,
            ).stdout
            descriptor = os.open(options.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "wb") as output:
                output.write(data)
            print(f"Configuration recovered from {snapshot_id}; use this exact ID for restore. Review domains/project.")
        elif options.command == "backup":
            configuration = read_configuration(options.env_file)
            if Path(configuration["_ENV_FILE"]).is_relative_to(options.repository):
                raise ValueError("Keep the deployment environment file outside the encrypted backup repository.")
            validate_configuration(configuration)
            with operation_lock(configuration):
                snapshot(options, configuration)
        elif options.command == "restore":
            configuration = read_configuration(options.env_file)
            validate_configuration(configuration)
            with operation_lock(configuration):
                restore(options, configuration)
        elif options.command == "check":
            restic(options, "check", "--read-data")
        elif options.command == "prune":
            restic(
                options,
                "forget",
                "--host",
                "lms-sis",
                "--tag",
                "sis-v1",
                "--keep-daily",
                "7",
                "--keep-weekly",
                "4",
                "--keep-monthly",
                "12",
                "--prune",
            )
        else:
            restic(options, "snapshots", "--host", "lms-sis", "--tag", "sis-v1")
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"SIS backup operation failed: {exc}\n")


if __name__ == "__main__":
    main()
