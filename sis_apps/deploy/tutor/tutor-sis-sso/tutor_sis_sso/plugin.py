"""Keep SIS browser permissions opt-in without widening cookie domains."""

from importlib.metadata import version
from urllib.parse import urlsplit

from tutor import hooks

__version__ = version("tutor-sis-sso")


def trusted_origins(values, enable_https):
    if not isinstance(values, list):
        raise ValueError("SIS_SSO_ORIGINS must be a list of exact browser origins.")
    origins = []
    for value in values:
        if not isinstance(value, str) or any(character.isspace() for character in value):
            raise ValueError("SIS_SSO_ORIGINS entries must be URLs without whitespace.")
        parsed = urlsplit(value)
        if (
            parsed.scheme not in ("http", "https")
            or not parsed.hostname
            or "*" in parsed.netloc
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in ("", "/")
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("SIS_SSO_ORIGINS entries must be exact HTTP(S) origins without credentials or paths.")
        if enable_https and parsed.scheme != "https":
            raise ValueError("SIS_SSO_ORIGINS must use HTTPS when Tutor HTTPS is enabled.")
        host = parsed.hostname.encode("idna").decode("ascii")
        host = f"[{host}]" if ":" in host else host
        if parsed.port is not None and parsed.port != (443 if parsed.scheme == "https" else 80):
            host += f":{parsed.port}"
        origin = f"{parsed.scheme}://{host}"
        if origin not in origins:
            origins.append(origin)
    return origins


SETTINGS_PATCH = """
# Explicitly trusted SIS frontends; existing Open edX origins are preserved.
_SIS_SSO_ORIGINS = {{ SIS_SSO_ORIGINS | sis_trusted_origins(ENABLE_HTTPS) | tojson }}
LOGIN_REDIRECT_WHITELIST = list(LOGIN_REDIRECT_WHITELIST) + [
    origin.split("://", 1)[1] for origin in _SIS_SSO_ORIGINS
]
CORS_ORIGIN_WHITELIST = list(CORS_ORIGIN_WHITELIST) + _SIS_SSO_ORIGINS
CSRF_TRUSTED_ORIGINS = list(CSRF_TRUSTED_ORIGINS) + _SIS_SSO_ORIGINS
"""

hooks.Filters.CONFIG_DEFAULTS.add_item(("SIS_SSO_ORIGINS", []))
hooks.Filters.ENV_TEMPLATE_FILTERS.add_item(("sis_trusted_origins", trusted_origins))
hooks.Filters.ENV_PATCHES.add_item(("openedx-lms-production-settings", SETTINGS_PATCH))
