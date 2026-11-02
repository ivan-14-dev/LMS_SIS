#!/usr/bin/env python3
"""Create a disposable, real Compose installation for browser and persistence checks."""

import argparse
import json
import os
import secrets
import shlex
import socket
import subprocess
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from sisctl import ROOT, compose, configure, initialize, read_configuration, variants


def verify_backup(configuration, work):
    repository = work / "backup"
    password_file = work / "backup-password"
    with os.fdopen(os.open(password_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as output:
        output.write(secrets.token_urlsafe(48))
    command = [
        "python3",
        str(ROOT / "scripts/sis_backup.py"),
        "--repository",
        str(repository),
        "--password-file",
        str(password_file),
    ]
    checks = {}
    for variant in variants(configuration):
        code = (
            "import hashlib,json; from pathlib import Path; "
            "from django.db import connection; from django.contrib.auth import get_user_model; "
            f"connection.set_schema('pilot_{variant}'); "
            "user=get_user_model().objects.get(username='pilot-admin'); "
            "print(json.dumps({'users':get_user_model().objects.count(),"
            "'mfa':hashlib.sha256(user.mfa_secret.encode()).hexdigest()}))"
        )
        result = compose(
            configuration,
            "exec",
            "-T",
            "-w",
            f"/app/sis_{variant}",
            f"api-{variant}",
            "python",
            "manage.py",
            "shell",
            "-c",
            code,
            capture_output=True,
        )
        checks[variant] = (code, result.stdout.splitlines()[-1])
        compose(
            configuration,
            "exec",
            "-T",
            f"api-{variant}",
            "python",
            "-c",
            "from pathlib import Path; "
            "roots=('media','private_exam_copies','private_financial_documents'); "
            "[(Path('/data')/root/'restore-verification.txt').write_text('Synthetic restoration fixture') "
            "for root in roots]",
        )
    subprocess.run([*command, "--env-file", configuration["_ENV_FILE"], "backup"], check=True)
    restored_env = work / "restored.env"
    subprocess.run([*command, "recover-config", "--snapshot", "latest", "--output", str(restored_env)], check=True)
    restored = read_configuration(restored_env)
    restored["COMPOSE_PROJECT_NAME"] = f"sis-restore-check-{uuid.uuid4().hex[:12]}"
    restored_env.write_text(
        "\n".join(f"{key}={shlex.quote(value)}" for key, value in restored.items() if not key.startswith("_")) + "\n"
    )
    restore_command = [
        *command,
        "--env-file",
        str(restored_env),
        "restore",
        "--snapshot",
        "latest",
        "--confirm-empty-target",
    ]
    try:
        subprocess.run(restore_command, check=True)
        for variant, (code, expected) in checks.items():
            code += (
                "; roots=('media','private_exam_copies','private_financial_documents'); "
                "assert all((Path('/data')/root/'restore-verification.txt').read_text()"
                "=='Synthetic restoration fixture' for root in roots)"
            )
            result = compose(
                restored,
                "run",
                "--rm",
                "--no-deps",
                "-T",
                f"api-{variant}",
                "python",
                "manage.py",
                "shell",
                "-c",
                code,
                capture_output=True,
            )
            if result.stdout.splitlines()[-1] != expected:
                raise AssertionError(f"Restored {variant} accounts or encrypted MFA data differ.")
        refusal = subprocess.run(restore_command, capture_output=True)
        if refusal.returncode == 0 or b"is not empty" not in refusal.stderr:
            raise AssertionError("Restoration must refuse populated databases.")
        subprocess.run([*command, "check"], check=True)
        print("Encrypted backup, private files, MFA data and nonempty-target protection verified.")
    finally:
        compose(restored, "down", "--volumes", "--remove-orphans")


def free_port():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["secondaire", "superieur", "dual"], default="dual")
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument(
        "--keep",
        action="store_true",
        help="Keep this disposable stack for diagnosis; stop it afterward.",
    )
    parser.add_argument("--skip-browser", action="store_true")
    parser.add_argument("--verify-backup", action="store_true")
    options = parser.parse_args()
    work = options.work_dir.resolve()
    work.mkdir(parents=True, exist_ok=True, mode=0o700)
    env_file = work / ".env"
    if env_file.exists():
        parser.error("Use a fresh work directory; existing validation secrets must not be replaced.")
    jwks_file = work / "jwks.json"
    public_key = subprocess.check_output(
        [
            "node",
            "-e",
            "const {generateKeyPairSync}=require('crypto');"
            "const {publicKey}=generateKeyPairSync('rsa',{modulusLength:2048});"
            "console.log(JSON.stringify({keys:[{...publicKey.export({format:'jwk'}),kid:'validation',alg:'RS512'}]}));",
        ]
    )
    jwks_file.write_bytes(public_key)
    with patch("getpass.getpass", return_value=secrets.token_urlsafe(32)):
        configure(
            SimpleNamespace(
                env_file=env_file,
                domain="validation.localhost",
                local=True,
                mode=options.mode,
                lms_url="http://127.0.0.1:9",
                cms_url="http://127.0.0.1:9",
                jwks=jwks_file,
                oauth_client_id="installation-test",
                issuer=None,
                audience="installation-test",
                auth_mode="local",
            )
        )
    configuration = read_configuration(env_file)
    port = free_port()
    for name, value in list(configuration.items()):
        configuration[name] = value.replace(":8080", f":{port}")
    configuration.update(
        COMPOSE_PROJECT_NAME=f"sis-install-check-{uuid.uuid4().hex[:12]}",
        SIS_HTTP_PORT=str(port),
        SIS_HTTPS_PORT=str(free_port()),
        SIS_FRONTEND_IMAGE=f"lms-sis-frontend:verify-{options.mode}",
    )
    env_file.write_text(
        "\n".join(f"{name}={shlex.quote(value)}" for name, value in configuration.items() if not name.startswith("_"))
        + "\n"
    )
    password = secrets.token_urlsafe(24)
    credentials = work / "credentials.json"
    with os.fdopen(os.open(credentials, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as output:
        json.dump({"username": "pilot-admin", "password": password}, output)
    try:
        for variant in variants(configuration):
            institution = work / f"{variant}.json"
            institution.write_text(
                json.dumps(
                    {
                        "schema_name": f"pilot_{variant}",
                        "domain": f"{variant}.validation.localhost",
                        "institution": {
                            "nom": f"Installation {variant}",
                            "type": ("college" if variant == "secondaire" else "universite_publique"),
                            "adresse": "1 rue du Test",
                            "code_postal": "75000",
                            "ville": "Paris",
                            "telephone": "0100000000",
                            "email": "institution@example.test",
                        },
                        "admin": {
                            "username": "pilot-admin",
                            "email": "pilot-admin@example.test",
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            with patch("getpass.getpass", return_value=password):
                initialize(
                    configuration,
                    SimpleNamespace(variant=variant, institution=institution),
                )
            compose(
                configuration,
                "run",
                "--rm",
                "--no-deps",
                "-T",
                "-v",
                f"{institution}:/run/institution.json:ro",
                f"api-{variant}",
                "python",
                "manage.py",
                "bootstrap_institution",
                "--config",
                "/run/institution.json",
                "--password-stdin",
                input=b"not-used-for-existing-accounts\n",
            )
            for check in (("check", "--deploy"), ("makemigrations", "--check", "--dry-run", "--noinput")):
                compose(
                    configuration,
                    "run",
                    "--rm",
                    "--no-deps",
                    "-T",
                    f"api-{variant}",
                    "python",
                    "manage.py",
                    *check,
                )
        compose(configuration, "up", "-d", "--build", "--wait", "--wait-timeout", "180")
        for variant in variants(configuration):
            compose(
                configuration,
                "exec",
                "-T",
                f"api-{variant}",
                "python",
                "-m",
                "sis_common.probe",
            )
        if not options.skip_browser:
            subprocess.run(
                ["npx", "playwright", "test"],
                cwd=ROOT / "frontend-app-sis",
                check=True,
                env={
                    **os.environ,
                    "SIS_E2E_URL": configuration["FRONTEND_URL"],
                    "SIS_E2E_MODE": options.mode,
                    "SIS_E2E_CREDENTIALS": str(credentials),
                },
            )
        compose(
            configuration,
            "restart",
            *[f"api-{variant}" for variant in variants(configuration)],
        )
        compose(configuration, "up", "-d", "--no-build", "--wait")
        if options.verify_backup:
            verify_backup(configuration, work)
        print(f"Installation verified for {options.mode}. Configuration: {env_file}")
    finally:
        if not options.keep:
            compose(configuration, "down", "--volumes", "--remove-orphans")


if __name__ == "__main__":
    main()
