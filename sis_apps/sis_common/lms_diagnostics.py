"""Read-only contract diagnostics, never inferred from a heartbeat alone."""

from urllib.parse import urlsplit

import requests

CONTRACT = "sis-provisioning/v1"
REQUIRED_CAPABILITIES = {
    "lms": ("accounts", "enrollments", "teaching"),
    "cms": ("courses", "publication"),
}
CONFIGURATION_KEYS = ("EDX_LMS_URL", "EDX_CMS_URL", "EDX_OAUTH_CLIENT_ID", "EDX_OAUTH_CLIENT_SECRET")

UNAVAILABLE_MESSAGE = "Le fournisseur LMS/Studio n'est pas configuré. Aucune synchronisation n'est confirmée."


def unavailable_response():
    from rest_framework.response import Response

    return Response({"error": UNAVAILABLE_MESSAGE, "available": False}, status=503)


def public_endpoint(value):
    try:
        endpoint = urlsplit(value or "")
        if endpoint.scheme not in ("http", "https") or not endpoint.hostname:
            return ""
        host = endpoint.hostname
        if ":" in host:
            host = f"[{host}]"
        port = f":{endpoint.port}" if endpoint.port else ""
        return f"{endpoint.scheme}://{host}{port}"
    except (TypeError, ValueError):
        return ""


def configuration_report(configuration):
    missing = [key for key in CONFIGURATION_KEYS if not getattr(configuration, key, None)]
    return {
        "configured": not missing,
        "available": False,
        "connected": False,
        "missing_configuration": missing,
        "oauth_status": "unverified" if not missing else "unavailable",
        "webhook_status": "unverified",
        "lms_url": public_endpoint(getattr(configuration, "EDX_LMS_URL", None)),
        "cms_url": public_endpoint(getattr(configuration, "EDX_CMS_URL", None)),
    }


def check_health(client):
    checks = {}
    for service, base in (("lms", client.lms_url), ("cms", client.cms_url)):
        check = {"ok": False, "status": None, "contract_status": "unverified"}
        checks[service] = check
        if not base:
            check["contract_status"] = "unavailable"
            continue
        try:
            response = requests.get(
                f"{base}/heartbeat", timeout=5, verify=client.verify_ssl, allow_redirects=False,
            )
            check["status"] = response.status_code
            if response.status_code != 200:
                check["contract_status"] = "unavailable"
                continue
            response = requests.get(
                f"{base}/api/sis/v1/capabilities/",
                headers=client._headers(), timeout=5, verify=client.verify_ssl, allow_redirects=False,
            )
            check["contract_status"] = "unavailable"
            if response.status_code != 200:
                check["contract_http_status"] = response.status_code
                continue
            payload = response.json()
            if not isinstance(payload, dict) or payload.get("contract") != CONTRACT:
                check["contract_status"] = "incompatible"
                continue
            capabilities = payload.get("capabilities")
            if not isinstance(capabilities, dict):
                check["contract_status"] = "incompatible"
                continue
            check["missing_capabilities"] = [
                capability for capability in REQUIRED_CAPABILITIES[service]
                if capabilities.get(capability) is not True
            ]
            check["ok"] = not check["missing_capabilities"]
            check["contract_status"] = "ready" if check["ok"] else "forbidden"
        except (requests.RequestException, ValueError, KeyError):
            check["contract_status"] = "unavailable"
    return checks


def integration_health(configuration, client_factory):
    report = configuration_report(configuration)
    if not report["configured"]:
        return report
    try:
        checks = client_factory().health_check()
    except Exception:
        # Exception text can contain OAuth responses or credentials in configured URLs.
        report["diagnostic_status"] = "unavailable"
        return report
    report.update(checks)
    report["connected"] = report["available"] = all(
        isinstance(checks.get(service), dict)
        and checks[service].get("ok") is True
        and checks[service].get("contract_status") == "ready"
        for service in REQUIRED_CAPABILITIES
    )
    report["oauth_status"] = "valid" if report["available"] else "unverified"
    return report
