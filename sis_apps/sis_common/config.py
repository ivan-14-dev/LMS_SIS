"""Shared, security-sensitive configuration helpers for SIS projects."""

import os
import sys

import environ
from django.core.exceptions import ImproperlyConfigured


def load_environment(base_dir):
    """Prefer process variables, then the variant's .env, then the shared .env."""
    for path in (base_dir / ".env", base_dir.parent / ".env"):
        if path.is_file():
            environ.Env.read_env(path, overwrite=False)


def get_variant_environment(name, variant, default=None):
    return os.environ.get(f"{name}_{variant.upper()}", os.environ.get(name, default))


def get_sis_mode(variant):
    mode = os.environ.get("SIS_MODE", variant)
    if mode not in ("secondaire", "superieur", "dual"):
        raise ImproperlyConfigured("SIS_MODE doit être secondaire, superieur ou dual.")
    return mode


def get_database_configuration(variant):
    password = get_variant_environment("DB_PASSWORD", variant)
    if not password:
        if is_test_environment():
            password = "postgres"
        else:
            raise ImproperlyConfigured(f"DB_PASSWORD_{variant.upper()} ou DB_PASSWORD doit être défini.")
    return {
        "ENGINE": "django_tenants.postgresql_backend",
        "NAME": get_variant_environment("DB_NAME", variant, f"sis_{variant}"),
        "USER": get_variant_environment("DB_USER", variant, "postgres"),
        "PASSWORD": password,
        "HOST": get_variant_environment("DB_HOST", variant, "localhost"),
        "PORT": get_variant_environment("DB_PORT", variant, "5432"),
        "CONN_MAX_AGE": 60,
        "CONN_HEALTH_CHECKS": True,
    }


def is_test_environment() -> bool:
    """Return whether Django is being initialized for a test run."""
    return "pytest" in sys.modules or any(argument == "test" for argument in sys.argv)


def get_required_secret(name: str, *, test_value: str) -> str:
    """Read a required secret, allowing a deterministic value only in tests."""
    value = os.environ.get(name)
    if value:
        return value
    if is_test_environment():
        return test_value
    raise ImproperlyConfigured(f"La variable d'environnement {name} doit être définie.")


def get_lms_configuration(variant):
    """Local authentication can run without configuring an external LMS."""
    mode = os.environ.get("SIS_AUTH_MODE", "lms")
    if mode not in ("lms", "local"):
        raise ImproperlyConfigured("SIS_AUTH_MODE doit être lms ou local.")
    configuration = {
        "SIS_AUTH_MODE": mode,
        "EDX_LMS_URL": os.environ.get("EDX_LMS_URL", "http://localhost:8000" if mode == "lms" else ""),
        "EDX_CMS_URL": os.environ.get("EDX_CMS_URL", "http://localhost:8001" if mode == "lms" else ""),
    }
    for name, test_value in {
        "EDX_OAUTH_CLIENT_ID": f"sis-{variant}-test-client",
        "EDX_OAUTH_CLIENT_SECRET": "test-oauth-secret",
        "EDX_JWT_AUDIENCE": "sis-test-audience",
        "EDX_JWT_PUBLIC_SIGNING_JWK_SET": '{"keys":[]}',
    }.items():
        configuration[name] = (
            get_required_secret(name, test_value=test_value) if mode == "lms" else os.environ.get(name, "")
        )
    lms = configuration["EDX_LMS_URL"].rstrip("/")
    configuration["EDX_JWT_ISSUER"] = os.environ.get("EDX_JWT_ISSUER", f"{lms}/oauth2" if lms else "")
    return configuration


def get_bool_environment(name: str, default: bool = False) -> bool:
    """Read a boolean environment variable."""
    return os.environ.get(name, str(default)).lower() in ("true", "1", "yes")


def get_allowed_hosts() -> list[str]:
    """Read allowed hosts, requiring an explicit production configuration."""
    configured_hosts = os.environ.get("DJANGO_ALLOWED_HOSTS", "")
    if configured_hosts:
        return [host.strip() for host in configured_hosts.split(",") if host.strip()]
    if is_test_environment() or get_bool_environment("DJANGO_DEBUG"):
        return ["localhost", "127.0.0.1", "testserver"]
    raise ImproperlyConfigured(
        "DJANGO_ALLOWED_HOSTS doit être défini en production. "
        "Exemple: DJANGO_ALLOWED_HOSTS=sis.example.com,api.sis.example.com"
    )
