"""Generate fresh local fixture configuration, never start containers or load."""

import argparse
import base64
import json
import os
import secrets
import socket
import subprocess
from pathlib import Path

PREFIX = "sis-load-d0c25c75"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, help="New relative artifact directory")
    args = parser.parse_args()
    root = Path(args.output)
    if root.is_absolute() or ".." in root.parts or root.exists():
        parser.error("Use a new relative artifact directory.")
    os.umask(0o077)
    root.mkdir(mode=0o700)
    for name in ("output", "runtime", "runtime/logs", "runtime/static", "runtime/media", "runtime/scratch", "tls", "tls/server"):
        (root / name).mkdir(mode=0o700)
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    origin = f"https://load-secondaire.localhost:{port}"
    database_password, redis_password = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    common = {
        "SIS_VARIANT": "secondaire", "DJANGO_SETTINGS_MODULE": "config.settings",
        "SIS_LOAD_FIXTURE": PREFIX, "SIS_LOAD_ARTIFACTS": "/fixture", "SIS_LOAD_ORIGIN": origin,
        "DB_HOST": PREFIX + "-postgres", "DB_NAME": "sis_load_d0c25c75", "DB_USER": "sis_load",
        "DB_PASSWORD": database_password, "DB_PORT": "5432",
        "DJANGO_SECRET_KEY": secrets.token_urlsafe(64), "DJANGO_DEBUG": "false",
        "DJANGO_ALLOWED_HOSTS": "load-secondaire.localhost", "CORS_ALLOWED_ORIGINS": origin,
        "REDIS_URL": f"redis://:{redis_password}@{PREFIX}-redis:6379/1",
        "CELERY_BROKER_URL": f"redis://:{redis_password}@{PREFIX}-redis:6379/2",
        "CELERY_RESULT_BACKEND": f"redis://:{redis_password}@{PREFIX}-redis:6379/3",
        "EDX_LMS_URL": "https://disabled-lms.example.invalid", "EDX_CMS_URL": "https://disabled-cms.example.invalid",
        "EDX_OAUTH_CLIENT_ID": "disposable-fixture-only", "EDX_OAUTH_CLIENT_SECRET": secrets.token_urlsafe(32),
        "EDX_JWT_AUDIENCE": "disposable-fixture-only", "EDX_JWT_PUBLIC_SIGNING_JWK_SET": '{"keys":[]}',
        "WEBHOOK_SECRET": secrets.token_urlsafe(32),
        "FIELD_ENCRYPTION_KEY": base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(),
        "EMAIL_BACKEND": "django.core.mail.backends.locmem.EmailBackend",
        "LOG_DIR": "/runtime/logs", "STATIC_ROOT": "/runtime/static", "MEDIA_ROOT": "/runtime/media",
        "PRIVATE_EXAM_STORAGE_ROOT": "/runtime/exams", "PRIVATE_FINANCIAL_STORAGE_ROOT": "/runtime/financial",
        "TMPDIR": "/runtime/scratch", "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUNBUFFERED": "1",
        "PYTHONPATH": "/app:/app/sis_secondaire",
    }
    (root / "api.env").write_text("".join(f"{key}={value}\n" for key, value in common.items()))
    (root / "postgres.env").write_text(
        f"POSTGRES_USER=sis_load\nPOSTGRES_DB=sis_load_d0c25c75\nPOSTGRES_PASSWORD={database_password}\n"
    )
    (root / "redis.conf").write_text(
        "bind 0.0.0.0\nport 6379\nprotected-mode yes\nsave \"\"\nappendonly no\n"
        f"requirepass {redis_password}\nmaxmemory 96mb\nmaxmemory-policy noeviction\n"
    )
    tls = root / "tls"
    (tls / "server.ext").write_text(
        "basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\n"
        "subjectAltName=DNS:load-secondaire.localhost,IP:127.0.0.1\nextendedKeyUsage=serverAuth\n"
        "subjectKeyIdentifier=hash\nauthorityKeyIdentifier=keyid,issuer\n"
    )
    commands = [
        ["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "2",
         "-keyout", str(tls / "ca.key"), "-out", str(tls / "ca.crt"), "-subj", "/CN=Disposable SIS load CA",
         "-addext", "basicConstraints=critical,CA:TRUE", "-addext", "keyUsage=critical,keyCertSign,cRLSign"],
        ["openssl", "req", "-newkey", "rsa:2048", "-nodes",
         "-keyout", str(tls / "server/server.key"), "-out", str(tls / "server.csr"),
         "-subj", "/CN=load-secondaire.localhost"],
        ["openssl", "x509", "-req", "-in", str(tls / "server.csr"), "-CA", str(tls / "ca.crt"),
         "-CAkey", str(tls / "ca.key"), "-CAcreateserial", "-out", str(tls / "server/server.crt"),
         "-days", "2", "-extfile", str(tls / "server.ext")],
    ]
    for command in commands:
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    metadata = {
        "prefix": PREFIX, "origin": origin, "port": port, "artifacts": str(root.resolve()),
        "api": {"memory_mib": 1024, "cpus": 1.5, "workers": 2, "worker_class": "sync"},
        "postgres": {"memory_mib": 512, "cpus": 1}, "redis": {"memory_mib": 128, "cpus": 0.25},
        "network_internal": True, "workers_or_beat": False, "debug": False,
    }
    (root / "fixture.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(json.dumps(metadata))


if __name__ == "__main__":
    main()
