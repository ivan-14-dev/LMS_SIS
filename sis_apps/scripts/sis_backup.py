#!/usr/bin/env python3
"""Encrypted, local-only SIS snapshots and restoration into an empty deployment."""

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
import uuid
from pathlib import Path

from sisctl import ROOT, compose, read_configuration, variants

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
        with tempfile.TemporaryDirectory(prefix="sis-snapshot-") as temporary:
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
            manifest = {
                "format": 1,
                "variants": selected,
                "postgres_major": 16,
                "field_key_sha256": hashlib.sha256(configuration["FIELD_ENCRYPTION_KEY"].encode()).hexdigest(),
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
                "/snapshot",
                mounts=mounts,
            )
    finally:
        if stopped:
            compose(configuration, "up", "-d", "--no-build", "--wait", *stopped)
    restic(options, "check")


def restore(options, configuration):
    if not options.confirm_empty_target:
        raise ValueError("Restore requires --confirm-empty-target and a fresh deployment, never a live database.")
    selected = variants(configuration)
    manifest = json.loads(
        restic(
            options,
            "dump",
            options.snapshot,
            "/snapshot/database/manifest.json",
            capture_output=True,
        ).stdout
    )
    if manifest.get("format") != 1 or manifest.get("postgres_major") != 16 or manifest.get("variants") != selected:
        raise ValueError("Snapshot format, database version or SIS_MODE differs from this deployment.")
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
                "find /target -type f -print -quit",
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
            options.snapshot,
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
    finally:
        subprocess.run(["docker", "volume", "rm", staging], check=True, stdout=subprocess.DEVNULL)
    print("SIS database and files restored. Verify domains, then start and check this isolated deployment.")


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
    options = parser.parse_args()
    options.repository = options.repository.resolve()
    options.password_file = options.password_file.resolve(strict=True)
    if options.password_file.stat().st_mode & 0o077:
        parser.error("The backup password file must have permissions 0600 (or stricter).")
    if not options.password_file.read_text().strip():
        parser.error("The backup password file must not be empty.")
    if options.repository == options.password_file or options.repository in options.password_file.parents:
        parser.error("Keep the password file outside the encrypted backup repository.")
    options.repository.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        if options.command == "recover-config":
            data = restic(
                options,
                "dump",
                options.snapshot,
                "/snapshot/configuration/.env",
                capture_output=True,
            ).stdout
            descriptor = os.open(options.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "wb") as output:
                output.write(data)
            print("Configuration recovered without printing secrets. Review domains and COMPOSE_PROJECT_NAME.")
        elif options.command == "backup":
            snapshot(options, read_configuration(options.env_file))
        elif options.command == "restore":
            restore(options, read_configuration(options.env_file))
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
