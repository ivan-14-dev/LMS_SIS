#!/usr/bin/env python3
"""Installation and operations for the SIS Compose distribution."""

import argparse
import base64
import getpass
import json
import os
import re
import secrets
import shlex
import subprocess
import sys
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
        if not separator or not key.strip().replace("_", "").isalnum():
            raise ValueError(f"Invalid environment assignment at line {number}.")
        words = shlex.split(raw_value, comments=True)
        if len(words) > 1:
            raise ValueError(f"Quote the environment value at line {number}.")
        configuration[key.strip()] = words[0] if words else ""
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
    environment = {**os.environ, **kwargs.pop("env", {})}
    environment["SIS_ENV_FILE"] = configuration.get("_ENV_FILE", str(ROOT / ".env"))
    command = [
        "docker",
        "compose",
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
    jwks = json.loads(options.jwks.read_text(encoding="utf-8"))
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
    oauth_secret = getpass.getpass("LMS OAuth client secret: ")
    if not oauth_secret:
        raise ValueError("The LMS OAuth client secret is required.")
    if oauth_secret.startswith("$"):
        raise ValueError("The OAuth secret must not begin with '$', which Django interprets as a variable reference.")
    selected = "superieur" if options.mode == "superieur" else "secondaire"
    configuration = {
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
    for name in ("start", "stop", "status", "check"):
        commands.add_parser(name)
    commands.add_parser("preflight", help="Read-only card reference check on existing Compose databases.")
    options = parser.parse_args()
    try:
        if options.command == "configure":
            configure(options)
            return
        configuration = read_configuration(options.env_file)
        if options.command == "init":
            initialize(configuration, options)
        elif options.command == "start":
            compose(configuration, "up", "-d", "--build", "--wait")
        elif options.command == "stop":
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
            compose(configuration, "config", "--quiet")
            preflight_card_references(configuration)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"SIS operation failed: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
