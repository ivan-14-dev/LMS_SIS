"""Configure opt-in SIS browser permissions and signed assessment callbacks."""

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


def grade_targets(values):
    if not isinstance(values, list):
        raise ValueError("SIS_GRADE_WEBHOOK_TARGETS must be a list.")
    for target in values:
        if not isinstance(target, dict) or set(target) - {"url", "secret", "course_ids"}:
            raise ValueError("SIS grade targets accept only url, secret and course_ids.")
        url = target.get("url")
        secret = target.get("secret")
        if not isinstance(url, str) or any(character.isspace() for character in url):
            raise ValueError("SIS grade callback URLs must be exact HTTPS URLs.")
        try:
            parsed = urlsplit(url)
            port = parsed.port
        except ValueError:
            raise ValueError("SIS grade callback URL or port is invalid.") from None
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or "*" in parsed.netloc
            or parsed.username is not None
            or parsed.password is not None
            or parsed.fragment
        ):
            raise ValueError("SIS grade callback URLs require HTTPS without credentials or fragments.")
        if port is not None and not 1 <= port <= 65535:
            raise ValueError("SIS grade callback port is invalid.")
        if not isinstance(secret, str) or not secret.strip():
            raise ValueError("Each SIS grade callback requires a private signing secret.")
        courses = target.get("course_ids", [])
        if not isinstance(courses, list) or any(
            not isinstance(course, str) or not course.strip() for course in courses
        ):
            raise ValueError("SIS grade course_ids must be a list of nonempty course identifiers.")
    return values


SETTINGS_PATCH = """
# Explicitly trusted SIS frontends; existing Open edX origins are preserved.
_SIS_SSO_ORIGINS = {{ SIS_SSO_ORIGINS | sis_trusted_origins(ENABLE_HTTPS) | tojson }}
LOGIN_REDIRECT_WHITELIST = list(LOGIN_REDIRECT_WHITELIST) + [
    origin.split("://", 1)[1] for origin in _SIS_SSO_ORIGINS
]
CORS_ORIGIN_WHITELIST = list(CORS_ORIGIN_WHITELIST) + _SIS_SSO_ORIGINS
CSRF_TRUSTED_ORIGINS = list(CSRF_TRUSTED_ORIGINS) + _SIS_SSO_ORIGINS

_SIS_GRADE_TARGETS = {{ SIS_GRADE_WEBHOOK_TARGETS | default([]) | sis_grade_targets | tojson }}
if _SIS_GRADE_TARGETS:
    SIS_GRADE_WEBHOOK_TARGETS = _SIS_GRADE_TARGETS
    FEATURES["ENABLE_COURSE_ASSESSMENT_GRADE_CHANGE_SIGNAL"] = True
    if not any(
        app == "openedx.core.djangoapps.sis_grade_webhooks"
        or app.startswith("openedx.core.djangoapps.sis_grade_webhooks.")
        for app in INSTALLED_APPS
    ):
        INSTALLED_APPS = list(INSTALLED_APPS) + [
            "openedx.core.djangoapps.sis_grade_webhooks.apps.SisGradeWebhooksConfig"
        ]
"""

hooks.Filters.CONFIG_DEFAULTS.add_item(("SIS_SSO_ORIGINS", []))
hooks.Filters.CONFIG_DEFAULTS.add_item(("SIS_GRADE_WEBHOOK_TARGETS", []))
hooks.Filters.ENV_TEMPLATE_FILTERS.add_item(("sis_trusted_origins", trusted_origins))
hooks.Filters.ENV_TEMPLATE_FILTERS.add_item(("sis_grade_targets", grade_targets))
hooks.Filters.ENV_PATCHES.add_item(("openedx-lms-production-settings", SETTINGS_PATCH))
