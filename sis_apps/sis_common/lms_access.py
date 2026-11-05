"""Strict transport for service-owned LMS access decisions."""

import re
from urllib.parse import quote

import requests

from .lms_courses import course_parts, course_sync_requested_at


def set_course_access(client, course_key, username, *, kind, active, requested_at):
    course_parts(course_key)
    if kind not in ("enrollment", "teaching") or type(active) is not bool:
        raise ValueError("Type ou état d'accès LMS invalide.")
    if not isinstance(username, str) or re.fullmatch(r"[\w-]{2,30}", username) is None:
        raise ValueError("Identifiant utilisateur LMS invalide.")
    requested_at = course_sync_requested_at(requested_at)
    resource = "enrollments" if kind == "enrollment" else "teaching"
    response = requests.post(
        f"{client.lms_url}/api/sis/v1/courses/{quote(course_key, safe=':+')}/{resource}/{quote(username)}/",
        json={"is_active": active, "requested_at": requested_at.isoformat()},
        headers=client._headers(), timeout=client.timeout, verify=client.verify_ssl, allow_redirects=False,
    )
    response.raise_for_status()
    if response.status_code != 200:
        raise ValueError("Le LMS ne confirme pas la décision d'accès.")
    result = response.json()
    if (
        not isinstance(result, dict) or result.get("course_id") != course_key
        or result.get("username") != username or result.get("kind") != kind
        or result.get("is_active") is not active
        or not isinstance(result.get("requested_at"), str)
        or course_sync_requested_at(result["requested_at"]) != requested_at
        or (result.get("id") is not None and (type(result["id"]) is not int or result["id"] < 1))
    ):
        raise ValueError("La réponse LMS ne confirme pas l'identité, l'état et la version demandés.")
    return result
