"""Opt-in HTTP port adapter; not for production domains or ``tutor dev``."""

import re
from pathlib import Path
from urllib.parse import urlsplit

from tutor import hooks

__version__ = "0.1.1"


def hostname(value):
    return urlsplit(f"http://{value}").hostname


def local_hosts(enabled, port, https, web_proxy, binding, *hosts):
    if enabled is False:
        return {}
    if enabled is not True:
        raise ValueError("SIS_LOCAL_URLS_ENABLED must be a boolean.")
    if type(port) is not int or not 1024 <= port <= 65535:
        raise ValueError("SIS_LOCAL_URLS_PORT must be an unprivileged TCP port.")
    if https is not False or web_proxy is not False:
        raise ValueError("The local URL adapter requires HTTP without an external web proxy.")
    if binding != f"127.0.0.1:{port}":
        raise ValueError("CADDY_HTTP_PORT must bind the local URL port to 127.0.0.1.")
    result = {}
    for service, value in zip(("lms", "cms", "mfe", "meilisearch"), hosts, strict=True):
        if not isinstance(value, str) or not re.fullmatch(r"[a-z0-9.-]+:[0-9]+", value):
            raise ValueError(f"{service} requires a bare localhost hostname and explicit port.")
        parsed = urlsplit(f"http://{value}")
        host = parsed.hostname
        if (
            parsed.port != port
            or not host
            or not (host == "localhost" or host.endswith(".localhost"))
            or any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?", label) for label in host.split("."))
        ):
            raise ValueError(f"{service} must use a localhost hostname on the configured port.")
        result[service] = host
    return result


def validate_config(config):
    local_hosts(
        config["SIS_LOCAL_URLS_ENABLED"],
        config["SIS_LOCAL_URLS_PORT"],
        config["ENABLE_HTTPS"],
        config["ENABLE_WEB_PROXY"],
        config["CADDY_HTTP_PORT"],
        *(config.get(key, "") for key in ("LMS_HOST", "CMS_HOST", "MFE_HOST", "MEILISEARCH_HOST")),
    )


PREAMBLE = """
{% set local = sis_local_urls(
    SIS_LOCAL_URLS_ENABLED, SIS_LOCAL_URLS_PORT, ENABLE_HTTPS,
    ENABLE_WEB_PROXY, CADDY_HTTP_PORT, LMS_HOST, CMS_HOST, MFE_HOST | default(""),
    MEILISEARCH_HOST) %}
"""

CADDY_PATCH = PREAMBLE + """
{% if local %}
http_port {{ SIS_LOCAL_URLS_PORT }}
auto_https off
{% endif %}
"""

INDIGO_ASSETS_PATCH = PREAMBLE + """
{% if local and "indigo" in PLUGINS %}
# Indigo's legacy footer asks for unprefixed paths; serve its existing PNGs.
rewrite /static/images/tutor-logo.png /static/indigo/images/tutor-logo.png
rewrite /static/images/openedx-logo.png /static/indigo/images/openedx-logo.png
{% endif %}
"""


def settings_patch(service):
    return PREAMBLE + """
{% if local %}
ALLOWED_HOSTS = [{{ local['SERVICE'] | tojson }}, "SERVICE"]
SESSION_COOKIE_DOMAIN = {{ local['SERVICE'] | tojson }}
SHARED_COOKIE_DOMAIN = SESSION_COOKIE_DOMAIN
# The original proxy's forwarded port is 80; the validated Host carries our port.
USE_X_FORWARDED_PORT = False
{% endif %}
""".replace("SERVICE", service)


def normalize_init_callbacks(tasks):
    # Keep the separate development callback valid when public hosts carry a port.
    before = "{{ CMS_HOST }}:8001"
    after = "{{ (CMS_HOST | sis_local_hostname) if SIS_LOCAL_URLS_ENABLED else CMS_HOST }}:8001"
    return [
        (service, script.replace(before, after) if service == "lms" else script)
        for service, script in tasks
    ]


hooks.Filters.CONFIG_DEFAULTS.add_items([
    ("SIS_LOCAL_URLS_ENABLED", False),
    ("SIS_LOCAL_URLS_PORT", 59080),
])
hooks.Actions.CONFIG_LOADED.add()(validate_config)
hooks.Filters.ENV_TEMPLATE_VARIABLES.add_item(("sis_local_urls", local_hosts))
hooks.Filters.ENV_TEMPLATE_FILTERS.add_item(("sis_local_hostname", hostname))
hooks.Filters.ENV_TEMPLATE_ROOTS.add_item(str(Path(__file__).parent / "templates"))
hooks.Filters.ENV_PATTERNS_INCLUDE.add_item("local/docker-compose.prod.override.yml")
hooks.Filters.ENV_PATCHES.add_item(("caddyfile-global", CADDY_PATCH))
hooks.Filters.ENV_PATCHES.add_item(("caddyfile-lms", INDIGO_ASSETS_PATCH))
for _service in ("lms", "cms"):
    hooks.Filters.ENV_PATCHES.add_item(
        (f"openedx-{_service}-production-settings", settings_patch(_service)),
        priority=hooks.priorities.LOW,
    )
with hooks.Contexts.app("lms").enter():
    hooks.Filters.CLI_DO_INIT_TASKS.add(priority=hooks.priorities.LOW)(normalize_init_callbacks)
