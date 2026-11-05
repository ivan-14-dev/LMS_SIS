"""Fail-closed target and fixture checks shared by every load entry point."""

import json
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, build_opener


class ConfigurationError(ValueError):
    pass


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def opener(*handlers):
    # Never inherit a workstation proxy or forward credentials through a redirect.
    return build_opener(ProxyHandler({}), NoRedirects(), *handlers)


def origin(value):
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except (TypeError, ValueError):
        raise ConfigurationError("Invalid target origin.") from None
    if (
        parsed.scheme not in ("http", "https")
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
        or any(ord(char) < 33 for char in value)
        or "\\" in value
    ):
        raise ConfigurationError("Target must be an HTTP(S) origin without credentials or a path.")
    hostname = parsed.hostname.lower().rstrip(".")
    if hostname == "sis.validation.localhost" or port in (58623, 59080, 59082):
        raise ConfigurationError("This active/non-SIS deployment is forbidden for load testing.")
    if parsed.scheme == "http" and not (
        hostname in ("localhost", "127.0.0.1", "::1") or hostname.endswith(".localhost")
    ):
        raise ConfigurationError("Non-loopback targets require HTTPS.")
    return value.rstrip("/")


def api_path(value):
    if not isinstance(value, str):
        raise ConfigurationError("API paths must be strings.")
    decoded = unquote(value)
    parsed = urlsplit(value)
    if (
        not value.startswith("/api/v1/")
        or parsed.scheme
        or parsed.netloc
        or parsed.fragment
        or "\\" in decoded
        or any(ord(char) < 32 for char in decoded)
        or ".." in decoded.split("/")
        or "%" in decoded
    ):
        raise ConfigurationError("Only same-origin /api/v1/ paths are permitted.")
    return value


def read_seed(filename):
    try:
        path = Path(filename)
        if path.stat().st_mode & 0o077:
            raise ConfigurationError("Seed contains credentials: restrict its permissions to 0600.")
        if path.stat().st_size > 10 * 1024 * 1024:
            raise ConfigurationError("Seed exceeds the 10 MiB limit.")
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise ConfigurationError("Cannot read the synthetic JSON seed.") from None
    if not isinstance(data, dict):
        raise ConfigurationError("Seed must be a JSON object.")
    return data


def check_isolation(target, acknowledgement, seed):
    target = origin(target)
    if not acknowledgement or origin(acknowledgement) != target:
        raise ConfigurationError("Explicit --acknowledge-isolated-target must match the target origin.")
    environment = seed.get("environment", {})
    if (
        not isinstance(environment, dict)
        or environment.get("isolated") is not True
        or environment.get("synthetic") is not True
        or environment.get("origin") != target
        or not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", str(environment.get("id", "")))
    ):
        raise ConfigurationError("Seed must explicitly bind an isolated synthetic environment to this origin.")
    return target
