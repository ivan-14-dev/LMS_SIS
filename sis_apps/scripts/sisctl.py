#!/usr/bin/env python3
"""Installation and operations for the SIS Compose distribution."""

import argparse
import base64
import binascii
import fcntl
import getpass
import ipaddress
import json
import os
import re
import secrets
import shlex
import socket
import stat
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent


def read_configuration(path=None):
    path = path or ROOT / ".env"
    configuration = {}
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, separator, raw_value = line.partition("=")
        if not separator or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key.strip()):
            raise ValueError(f"Invalid environment assignment at line {number}.")
        if key.strip() in configuration:
            raise ValueError(f"Duplicate environment assignment at line {number}.")
        raw_value = raw_value.strip()
        if raw_value.startswith(("'", '"')):
            quote = raw_value[0]
            value, closing, suffix = raw_value[1:].partition(quote)
            if not closing or (suffix.strip() and not suffix.lstrip().startswith("#")):
                raise ValueError(f"Use one literal quoted environment value at line {number}.")
            if quote == '"' and any(character in value for character in "\\$"):
                raise ValueError(f"Use single quotes for literal '$' or backslashes at line {number}.")
        else:
            value = re.split(r"\s+#", raw_value, maxsplit=1)[0]
            if value.startswith("#"):
                value = ""
            if any(character.isspace() or character in "'\"\\$" for character in value):
                raise ValueError(f"Use a literal single-quoted environment value at line {number}.")
        configuration[key.strip()] = value
    configuration["_ENV_FILE"] = str(path.resolve())
    return configuration


def variants(configuration):
    mode = configuration.get("SIS_MODE", "secondaire")
    if mode == "dual":
        return ["secondaire", "superieur"]
    if mode not in ("secondaire", "superieur"):
        raise ValueError("SIS_MODE must be secondaire, superieur or dual.")
    return [mode]


def deployment_url(value, label, local):
    url = value.rstrip("/")
    parsed = urlparse(url)
    schemes = ("http", "https") if local else ("https",)
    if (
        parsed.scheme not in schemes
        or not parsed.hostname
        or any(character.isspace() for character in url)
        or parsed.username
        or parsed.password
        or parsed.path
        or parsed.params
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(f"{label} URL must be a complete {'HTTP(S)' if local else 'HTTPS'} origin.")
    try:
        if parsed.port == 0:
            raise ValueError("Port zero is not a service port.")
    except ValueError as exc:
        raise ValueError(f"{label} URL must use a valid service port.") from exc
    return url


def compose(configuration, *arguments, **kwargs):
    # Shell overrides must not redirect an operation to another deployment or key.
    interpolation = set(re.findall(r"\$\{([A-Z_][A-Z_0-9]*)", (ROOT / "compose.yaml").read_text()))
    environment = {
        key: value for key, value in os.environ.items()
        if key not in interpolation and not key.startswith("COMPOSE_")
    }
    environment.update({
        key: value for key, value in configuration.items()
        if not key.startswith("_") and not key.startswith("COMPOSE_")
    })
    environment.update(kwargs.pop("env", {}))
    environment["COMPOSE_PROJECT_NAME"] = project_name(configuration)
    environment["COMPOSE_PROFILES"] = ""
    environment["SIS_ENV_FILE"] = configuration.get("_ENV_FILE", str(ROOT / ".env"))
    command = [
        "docker",
        "compose",
        "--project-name",
        project_name(configuration),
        "--project-directory",
        str(ROOT),
        "-f",
        str(ROOT / "compose.yaml"),
        "--env-file",
        environment["SIS_ENV_FILE"],
    ]
    for variant in variants(configuration):
        command.extend(["--profile", variant])
    return subprocess.run([*command, *arguments], check=True, env=environment, **kwargs)


def project_name(configuration):
    name = configuration.get("COMPOSE_PROJECT_NAME", "lms-sis")
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", name):
        raise ValueError("COMPOSE_PROJECT_NAME must contain lowercase letters, digits, hyphens or underscores.")
    return name


@contextmanager
def operation_lock(configuration):
    """Serialize maintenance using the private configuration directory, not /tmp."""
    directory = Path(configuration["_ENV_FILE"]).resolve().parent
    lock = directory / f".{project_name(configuration)}.operations.lock"
    descriptor = os.open(lock, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError("Another SIS maintenance operation is running for this configuration/project.") from exc
        yield


def validate_configuration(configuration):
    """Offline checks only: no Docker, remote requests or secret values in errors."""
    selected = variants(configuration)
    project_name(configuration)
    path = Path(configuration["_ENV_FILE"])
    if not path.is_file() or stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise ValueError("The deployment environment file must be a regular private file (0600 or stricter).")
    required = [
        "DJANGO_SECRET_KEY", "FIELD_ENCRYPTION_KEY", "WEBHOOK_SECRET",
        "DB_PASSWORD_SECONDAIRE", "DB_PASSWORD_SUPERIEUR",
        "EDX_OAUTH_CLIENT_ID", "EDX_OAUTH_CLIENT_SECRET", "EDX_JWT_ISSUER",
        "EDX_JWT_AUDIENCE", "EDX_JWT_PUBLIC_SIGNING_JWK_SET",
    ]
    for key in required:
        if not configuration.get(key) or configuration[key].startswith("$"):
            raise ValueError(f"{key} is required and must be a literal value, not a variable reference.")
    for key in ("DJANGO_SECRET_KEY", "WEBHOOK_SECRET", "DB_PASSWORD_SECONDAIRE", "DB_PASSWORD_SUPERIEUR"):
        if len(configuration[key]) < 32:
            raise ValueError(f"{key} must contain at least 32 characters; preserve existing encryption keys.")
    try:
        decoded = base64.b64decode(configuration["FIELD_ENCRYPTION_KEY"], altchars=b"-_", validate=True)
        if len(decoded) != 32:
            raise ValueError
    except (ValueError, binascii.Error) as exc:
        raise ValueError(
            "FIELD_ENCRYPTION_KEY must be a URL-safe base64-encoded 32-byte key; do not regenerate it."
        ) from exc
    validate_jwks(configuration["EDX_JWT_PUBLIC_SIGNING_JWK_SET"])
    if configuration.get("SIS_AUTH_MODE", "lms") not in ("lms", "local"):
        raise ValueError("SIS_AUTH_MODE must be lms or local.")
    debug = configuration.get("DJANGO_DEBUG", "False").lower()
    if debug not in ("true", "false", "1", "0", "yes", "no"):
        raise ValueError("DJANGO_DEBUG must be True/False, 1/0 or yes/no.")
    local = debug in ("true", "1", "yes")
    try:
        binding = ipaddress.ip_address(configuration.get("SIS_BIND_ADDRESS", "127.0.0.1"))
    except ValueError as exc:
        raise ValueError("SIS_BIND_ADDRESS must be an explicit IP address.") from exc
    if local and not binding.is_loopback:
        raise ValueError("DEBUG/local HTTP deployments must bind to a loopback address, never a public interface.")
    ports = [configuration.get("SIS_HTTP_PORT", "8080"), configuration.get("SIS_HTTPS_PORT", "8443")]
    if any(not port.isdigit() or not 1 <= int(port) <= 65535 for port in ports) or int(ports[0]) == int(ports[1]):
        raise ValueError("SIS_HTTP_PORT and SIS_HTTPS_PORT must be distinct ports between 1 and 65535.")
    for key in ("EDX_LMS_URL", "EDX_CMS_URL", "FRONTEND_URL"):
        deployment_url(configuration.get(key, ""), key, local)
    for variant in ("SECONDAIRE", "SUPERIEUR", "ADMIN"):
        key = f"SIS_{variant}_API_URL"
        value = configuration.get(key, "")
        if not value.endswith("/api/v1"):
            raise ValueError(f"{key} must end with /api/v1.")
        deployment_url(value.removesuffix("/api/v1"), key, local)
    for label, url_key in (
        ("FRONTEND", "FRONTEND_URL"),
        ("SECONDAIRE", "SIS_SECONDAIRE_API_URL"),
        ("SUPERIEUR", "SIS_SUPERIEUR_API_URL"),
    ):
        address = deployment_url(configuration.get(f"SIS_{label}_ADDRESS", ""), f"SIS_{label}_ADDRESS", local)
        public = urlparse(configuration[url_key])
        gateway = urlparse(address)
        if (public.scheme, public.hostname) != (gateway.scheme, gateway.hostname):
            raise ValueError(f"SIS_{label}_ADDRESS must match the public URL scheme and hostname.")
    hosts = [host.strip() for host in configuration.get("DJANGO_ALLOWED_HOSTS", "").split(",")]
    if "*" in hosts:
        raise ValueError("DJANGO_ALLOWED_HOSTS must name explicit API domains, not '*'.")
    for variant in selected:
        hostname = urlparse(configuration[f"SIS_{variant.upper()}_API_URL"]).hostname
        if hostname not in hosts and not any(
            host.startswith(".") and (hostname == host[1:] or hostname.endswith(host))
            for host in hosts
        ):
            raise ValueError(f"DJANGO_ALLOWED_HOSTS must include the {variant} API hostname.")
    if not local and configuration.get("EMAIL_BACKEND") != "django.core.mail.backends.smtp.EmailBackend":
        print("WARNING: production SMTP is not configured; account recovery/email delivery is not qualified.")
    concurrency = configuration.get("SIS_WORKER_CONCURRENCY", "2")
    if not concurrency.isdigit() or not 1 <= int(concurrency) <= 64:
        raise ValueError("SIS_WORKER_CONCURRENCY must be an integer between 1 and 64.")
    print(
        f"Configuration valid for project {project_name(configuration)} ({', '.join(selected)}); secrets not printed."
    )


def validate_jwks(raw):
    try:
        jwks = json.loads(raw)
    except ValueError as exc:
        raise ValueError("EDX_JWT_PUBLIC_SIGNING_JWK_SET must contain valid JSON.") from exc
    keys = jwks.get("keys") if isinstance(jwks, dict) else None
    if not isinstance(keys, list) or not keys:
        raise ValueError("Provide the LMS public signing JWKS, containing at least one key.")
    private_fields = {"d", "p", "q", "dp", "dq", "qi", "oth"}
    if any(
        not isinstance(key, dict)
        or key.get("kty") != "RSA"
        or private_fields.intersection(key)
        or not all(isinstance(key.get(field), str) and key[field] for field in ("n", "e"))
        for key in keys
    ):
        raise ValueError("Only public RSA signing keys belong in the SIS JWKS.")
    return jwks


def installation_preflight(configuration, *, check_ports=False):
    validate_configuration(configuration)
    try:
        result = subprocess.run(
            ["docker", "compose", "version", "--short"], check=True, capture_output=True, text=True, timeout=15,
        )
        version = re.match(r"v?(\d+)\.(\d+)", result.stdout.strip())
        if not version or tuple(map(int, version.groups())) < (2, 20):
            raise ValueError("Docker Compose >= 2.20 is required for this installation.")
        subprocess.run(["docker", "info"], check=True, capture_output=True, timeout=15)
        compose(configuration, "config", "--quiet", capture_output=True, timeout=30)
        if configuration.get("SIS_LMS_NETWORK_EXTERNAL", "false").lower() == "true":
            network = configuration.get("SIS_LMS_NETWORK", f"{project_name(configuration)}_lms")
            subprocess.run(
                ["docker", "network", "inspect", network], check=True, capture_output=True, timeout=15,
            )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValueError(
            "Docker/Compose preflight failed: verify the daemon, access permissions, Compose configuration "
            "and any external SIS_LMS_NETWORK. No container was started."
        ) from exc
    if check_ports:
        binding = configuration.get("SIS_BIND_ADDRESS", "127.0.0.1")
        family = socket.AF_INET6 if ":" in binding else socket.AF_INET
        for key, default in (("SIS_HTTP_PORT", "8080"), ("SIS_HTTPS_PORT", "8443")):
            try:
                with socket.socket(family, socket.SOCK_STREAM) as listener:
                    listener.bind((binding, int(configuration.get(key, default))))
            except OSError as exc:
                raise ValueError(
                    f"{key} cannot be bound; choose a free port/address without stopping another service."
                ) from exc
    print("Docker/Compose preflight passed. DNS, certificate issuance, LMS and SMTP still require live qualification.")


def service_status(configuration):
    raw = compose(
        configuration, "ps", "--all", "--format", "json", capture_output=True, text=True, timeout=30,
    ).stdout.strip()
    if not raw:
        return []
    try:
        data = json.loads(raw)
        records = data if isinstance(data, list) else [data]
    except ValueError:
        records = [json.loads(line) for line in raw.splitlines() if line.strip()]
    if not all(isinstance(record, dict) and record.get("Service") for record in records):
        raise ValueError("Invalid Compose service status response.")
    return records


def doctor(configuration):
    installation_preflight(configuration)
    records = service_status(configuration)
    expected = ["redis", "frontend", "gateway"] + [
        f"{role}-{variant}" for variant in variants(configuration) for role in ("postgres", "api", "worker", "beat")
    ]
    failed = []
    for service in expected:
        instances = [record for record in records if record["Service"] == service]
        if not instances:
            print(f"FAIL {service}: missing; initialize/start this project first.")
            failed.append(service)
        for instance in instances:
            state, health = instance.get("State", "unknown"), instance.get("Health", "")
            healthy = state == "running" and (
                health == "healthy" or (service == "gateway" or service.startswith("beat-")) and not health
            )
            print(f"{'OK' if healthy else 'FAIL'} {service}: state={state}, health={health or 'not configured'}")
            if not healthy:
                failed.append(service)
        if service.startswith("beat-") and len(instances) > 1:
            print(f"FAIL {service}: multiple schedulers can publish duplicate tasks; keep exactly one.")
            failed.append(service)
    print("Beat process status is not proof of scheduling; verify task/outbox age and a controlled periodic task.")
    if failed:
        raise ValueError("Runtime diagnosis failed; inspect the named services privately. No service was changed.")


def update(configuration, options):
    if not options.confirm_backup:
        raise ValueError(
            "Update requires --confirm-backup after verifying a restorable snapshot and recording old image IDs."
        )
    installation_preflight(configuration)
    selected = variants(configuration)
    running = {
        record["Service"] for record in service_status(configuration) if record.get("State") == "running"
    }
    if any(f"postgres-{variant}" not in running for variant in selected) or "redis" not in running:
        raise ValueError("Update requires the existing databases and Redis running; use init for a new installation.")
    if not getattr(options, "no_build", False):
        # All API/worker variants share one backend image; build it only once.
        compose(configuration, "build", f"api-{selected[0]}")
        compose(configuration, "build", "frontend")
    writers = [f"{role}-{variant}" for variant in selected for role in ("api", "worker", "beat")]
    compose(configuration, "stop", "--timeout", "120", *writers)
    try:
        preflight_card_references(configuration)
        for variant in selected:
            for arguments in (
                ("migrate_schemas", "--shared", "--noinput"),
                ("migrate_schemas", "--tenant", "--noinput"),
                ("collectstatic", "--noinput"),
                ("check",),
            ):
                compose(
                    configuration, "run", "--rm", "--no-deps", "-T",
                    f"api-{variant}", "python", "manage.py", *arguments,
                )
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        raise ValueError(
            "Update failed; API/workers/Beat remain stopped. Do not start old code on partially migrated databases. "
            "Inspect the failure or restore the verified snapshot into a separate project."
        ) from exc
    compose(configuration, "up", "-d", "--no-build", "--wait")
    doctor(configuration)
    print("Update finished for all tenant schemas; administrator identities/passwords were not reprovisioned.")


def preflight_card_references(configuration):
    """Check existing tenant payment tables before adding the card reference indexes."""
    conflicts = []
    for variant in variants(configuration):
        table = "paiements_paiement" if variant == "secondaire" else "paiements_paiementfrais"
        database = configuration.get(f"DB_NAME_{variant.upper()}", f"sis_{variant}")
        user = configuration.get("DB_USER", "sis")
        service = f"postgres-{variant}"

        def query(sql):
            try:
                result = compose(
                    configuration,
                    "exec", "-T", service,
                    "psql", "-X", "-w", "-A", "-t", "-v", "ON_ERROR_STOP=1",
                    "-U", user, "-d", database, "-c", sql,
                    capture_output=True,
                    text=True,
                )
            except subprocess.CalledProcessError as exc:
                raise ValueError(
                    f"Cannot inspect {variant} payments; verify that its database is running and accessible. "
                    "No migration was attempted."
                ) from exc
            return result.stdout.strip()

        schemas = query(
            "SELECT n.nspname FROM pg_catalog.pg_namespace n "
            "JOIN pg_catalog.pg_class c ON c.relnamespace = n.oid "
            f"WHERE c.relname = '{table}' AND c.relkind IN ('r', 'p') "
            "AND n.nspname <> 'public' AND left(n.nspname, 3) <> 'pg_' "
            "AND n.nspname <> 'information_schema' ORDER BY n.nspname"
        ).splitlines()
        variant_conflicts = []
        for schema in schemas:
            quoted_schema = '"' + schema.replace('"', '""') + '"'
            result = query(
                "WITH duplicates AS ("
                " SELECT array_agg(id ORDER BY id) AS ids, min(id) AS first_id"
                f" FROM {quoted_schema}.\"{table}\""
                " WHERE mode = 'carte' AND statut IN ('valide', 'rembourse')"
                " AND reference_externe <> ''"
                " GROUP BY reference_externe HAVING count(*) > 1"
                ") SELECT json_build_object("
                " 'count', count(*),"
                " 'samples', coalesce((SELECT json_agg(ids) FROM"
                " (SELECT ids FROM duplicates ORDER BY first_id LIMIT 5) samples), '[]'::json)"
                ") FROM duplicates"
            )
            try:
                report = json.loads(result)
                count, samples = report["count"], report["samples"]
                if not isinstance(count, int) or not isinstance(samples, list):
                    raise ValueError("Invalid database response.")
            except (ValueError, KeyError, TypeError) as exc:
                raise ValueError(f"Invalid payment preflight response for {variant}/{schema}.") from exc
            if count:
                variant_conflicts.append(
                    f"{variant}/{schema}: {count} duplicate reference(s); payment IDs (up to 5 groups): {samples}"
                )
        conflicts.extend(variant_conflicts)
        if not variant_conflicts:
            print(f"Card reference preflight passed for {variant} ({len(schemas)} existing payment schema(s)).")
    if conflicts:
        raise ValueError(
            "Card reference migration blocked: " + "; ".join(conflicts)
            + ". Reconcile the payments manually on a restored copy before retrying; no records were changed."
        )


def configure(options):
    destination = options.env_file
    if destination.exists():
        raise ValueError(f"{destination} already exists; edit it rather than replacing its secrets.")
    domain = options.domain.strip().lower()
    if len(domain) > 253 or not all(
        re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in domain.split(".")
    ):
        raise ValueError("Use a DNS domain without scheme, port or path.")
    if not options.local and domain.endswith(".localhost"):
        raise ValueError("Use --local for a localhost-only installation.")
    scheme = "http" if options.local else "https"
    port = ":8080" if options.local else ""
    lms = deployment_url(options.lms_url, "LMS", options.local)
    cms = deployment_url(options.cms_url, "Studio", options.local)
    jwks = validate_jwks(options.jwks.read_text(encoding="utf-8"))
    oauth_secret = getpass.getpass("LMS OAuth client secret: ")
    if not oauth_secret:
        raise ValueError("The LMS OAuth client secret is required.")
    if oauth_secret.startswith("$"):
        raise ValueError("The OAuth secret must not begin with '$', which Django interprets as a variable reference.")
    selected = "superieur" if options.mode == "superieur" else "secondaire"
    configuration = {
        "COMPOSE_PROJECT_NAME": project_name({"COMPOSE_PROJECT_NAME": getattr(options, "project_name", "lms-sis")}),
        "SIS_MODE": options.mode,
        "SIS_AUTH_MODE": options.auth_mode,
        "DJANGO_SECRET_KEY": secrets.token_urlsafe(48),
        "DJANGO_DEBUG": str(options.local),
        "DJANGO_ALLOWED_HOSTS": f"secondaire.{domain},superieur.{domain}",
        "DB_USER": "sis",
        "DB_NAME_SECONDAIRE": "sis_secondaire",
        "DB_NAME_SUPERIEUR": "sis_superieur",
        "DB_PASSWORD_SECONDAIRE": secrets.token_urlsafe(32),
        "DB_PASSWORD_SUPERIEUR": secrets.token_urlsafe(32),
        "FIELD_ENCRYPTION_KEY": base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(),
        "WEBHOOK_SECRET": secrets.token_urlsafe(32),
        "EDX_LMS_URL": lms,
        "EDX_CMS_URL": cms,
        "EDX_OAUTH_CLIENT_ID": options.oauth_client_id,
        "EDX_OAUTH_CLIENT_SECRET": oauth_secret,
        "EDX_JWT_ISSUER": options.issuer or f"{lms}/oauth2",
        "EDX_JWT_AUDIENCE": options.audience,
        "EDX_JWT_PUBLIC_SIGNING_JWK_SET": json.dumps(jwks, separators=(",", ":")),
        "FRONTEND_URL": f"{scheme}://sis.{domain}{port}",
        "SIS_SECONDAIRE_API_URL": f"{scheme}://secondaire.{domain}{port}/api/v1",
        "SIS_SUPERIEUR_API_URL": f"{scheme}://superieur.{domain}{port}/api/v1",
        "SIS_ADMIN_API_URL": f"{scheme}://{selected}.{domain}{port}/api/v1",
        "CORS_ALLOWED_ORIGINS": f"{scheme}://sis.{domain}{port},{lms}",
        "SIS_FRONTEND_ADDRESS": f"{scheme}://sis.{domain}",
        "SIS_SECONDAIRE_ADDRESS": f"{scheme}://secondaire.{domain}",
        "SIS_SUPERIEUR_ADDRESS": f"{scheme}://superieur.{domain}",
        "SIS_BIND_ADDRESS": "127.0.0.1" if options.local else "0.0.0.0",
        "SIS_HTTP_PORT": "8080" if options.local else "80",
        "SIS_HTTPS_PORT": "8443" if options.local else "443",
    }
    for key, value in configuration.items():
        if any(character in value for character in "'\r\n\0"):
            raise ValueError(f"{key} must be a single-line value without single quotes.")
    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as output:
        output.write("\n".join(f"{key}={shlex.quote(value)}" for key, value in configuration.items()) + "\n")
    print(f"Configuration written to {destination}. Secrets were not printed.")


def initialize(configuration, options):
    if options.variant not in variants(configuration):
        raise ValueError("The requested variant is disabled by SIS_MODE.")
    path = options.institution.resolve(strict=True)
    # Validate JSON before starting any containers.
    institution = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(institution, dict)
        or not isinstance(institution.get("schema_name"), str)
        or not isinstance(institution.get("domain"), str)
        or not isinstance(institution.get("institution"), dict)
        or not isinstance(institution.get("admin"), dict)
    ):
        raise ValueError("Institution JSON requires schema_name, domain, institution and admin.")
    schema = institution["schema_name"]
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", schema) or schema == "public":
        raise ValueError(
            "schema_name must be a non-public lowercase PostgreSQL identifier: "
            "use 1-63 letters, digits or underscores, starting with a letter."
        )
    compose(configuration, "config", "--quiet")
    compose(configuration, "build", f"api-{options.variant}")
    compose(configuration, "up", "-d", "--wait", f"postgres-{options.variant}", "redis")
    preflight_card_references({**configuration, "SIS_MODE": options.variant})
    password = getpass.getpass("Initial SIS administrator password (existing passwords are preserved): ")
    compose(
        configuration,
        "run",
        "--rm",
        "--no-deps",
        "-T",
        "-v",
        f"{path}:/run/institution.json:ro",
        f"api-{options.variant}",
        "python",
        "manage.py",
        "bootstrap_institution",
        "--config",
        "/run/institution.json",
        "--password-stdin",
        input=(password + "\n").encode(),
    )
    compose(
        configuration,
        "run",
        "--rm",
        "--no-deps",
        "-T",
        f"api-{options.variant}",
        "python",
        "manage.py",
        "collectstatic",
        "--noinput",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    commands = parser.add_subparsers(dest="command", required=True)
    setup = commands.add_parser(
        "configure",
        help="Generate private deployment configuration; never overwrite secrets.",
    )
    setup.add_argument("--mode", choices=["secondaire", "superieur", "dual"], default="secondaire")
    setup.add_argument("--project-name", default="lms-sis", help="Unique Compose project on this Docker host.")
    setup.add_argument("--domain", required=True)
    setup.add_argument("--lms-url", required=True)
    setup.add_argument("--cms-url", required=True)
    setup.add_argument("--jwks", required=True, type=Path)
    setup.add_argument("--oauth-client-id", default="sis-integration")
    setup.add_argument("--audience", default="openedx")
    setup.add_argument("--issuer")
    setup.add_argument("--local", action="store_true")
    setup.add_argument("--auth-mode", choices=["lms", "local"], default="lms")
    initial = commands.add_parser("init", help="Provision a variant using an institution JSON document.")
    initial.add_argument("--variant", required=True, choices=["secondaire", "superieur"])
    initial.add_argument("--institution", required=True, type=Path)
    start = commands.add_parser("start")
    start.add_argument("--no-build", action="store_true", help="Use already available, explicitly selected images.")
    for name in ("stop", "status", "check"):
        commands.add_parser(name)
    preflight = commands.add_parser("preflight", help="Read-only checks; default checks existing payment references.")
    preflight.add_argument("--installation", action="store_true", help="Check configuration and Docker, not databases.")
    preflight.add_argument("--offline", action="store_true", help="Check configuration only; never contact Docker.")
    preflight.add_argument(
        "--ports", action="store_true", help="With --installation, check gateway ports are available."
    )
    commands.add_parser("doctor", help="Read-only service/worker diagnosis; nonzero exit if unhealthy.")
    upgrade = commands.add_parser(
        "update", help="Migrate all tenant schemas in maintenance, without resetting accounts."
    )
    upgrade.add_argument(
        "--confirm-backup", action="store_true", help="Attest a restorable snapshot and old images exist."
    )
    upgrade.add_argument("--no-build", action="store_true", help="Use prepared release images rather than rebuilding.")
    options = parser.parse_args()
    try:
        if options.command == "configure":
            configure(options)
            return
        configuration = read_configuration(options.env_file)
        if options.command in ("init", "start", "update", "stop"):
            with operation_lock(configuration):
                if options.command == "init":
                    installation_preflight(configuration)
                    initialize(configuration, options)
                elif options.command == "start":
                    installation_preflight(configuration)
                    compose(
                        configuration, "up", "-d", "--no-build" if options.no_build else "--build", "--wait",
                    )
                elif options.command == "update":
                    update(configuration, options)
                else:
                    compose(configuration, "stop")
        elif options.command == "status":
            compose(configuration, "ps")
        elif options.command == "check":
            compose(configuration, "config", "--quiet")
            for variant in variants(configuration):
                compose(
                    configuration,
                    "exec",
                    "-T",
                    "-w",
                    f"/app/sis_{variant}",
                    f"api-{variant}",
                    "python",
                    "manage.py",
                    "check",
                    "--deploy",
                )
        elif options.command == "preflight":
            if options.installation and options.offline:
                raise ValueError("Choose --installation or --offline, not both.")
            if options.ports and (not options.installation or options.offline):
                raise ValueError("--ports requires --installation and cannot be combined with --offline.")
            if options.offline:
                validate_configuration(configuration)
            else:
                installation_preflight(configuration, check_ports=options.ports)
                if not options.installation:
                    preflight_card_references(configuration)
        elif options.command == "doctor":
            doctor(configuration)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"SIS operation failed: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
