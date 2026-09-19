"""Shared, security-sensitive configuration helpers for SIS projects."""

import os
import sys

from django.core.exceptions import ImproperlyConfigured


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
