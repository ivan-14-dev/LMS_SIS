"""Enrollment API v1 contract shared by both SIS variants."""

from urllib.parse import parse_qs, urljoin, urlsplit

import requests


def set_enrollment(client, course_key, username, *, active, mode=None):
    data = {
        "user": username,
        "course_details": {"course_id": course_key},
        "is_active": active,
    }
    if mode is not None:
        data["mode"] = mode
    response = requests.post(
        f"{client.lms_url}/api/enrollment/v1/enrollment",
        json=data,
        headers=client._headers(),
        timeout=client.timeout,
        verify=client.verify_ssl,
        allow_redirects=False,
    )
    response.raise_for_status()
    if response.status_code != 200:
        raise ValueError("La réponse LMS ne confirme pas l'inscription demandée.")
    result = response.json()
    if (
        not isinstance(result, dict)
        or result.get("user") != username
        or not isinstance(result.get("course_details"), dict)
        or result["course_details"].get("course_id") != course_key
        or result.get("is_active") is not active
        or (mode is not None and result.get("mode") != mode)
    ):
        raise ValueError("La réponse LMS ne confirme pas l'inscription demandée.")
    return result


def course_enrollments(client, course_key):
    endpoint = f"{client.lms_url}/api/enrollment/v1/enrollments"
    origin = urlsplit(endpoint)
    url = endpoint
    params = {"course_id": course_key}
    results = []
    seen = set()
    while True:
        response = requests.get(
            url,
            params=params,
            headers=client._headers(),
            timeout=client.timeout,
            verify=client.verify_ssl,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or not isinstance(payload.get("results"), list) or "next" not in payload:
            raise ValueError("La réponse LMS ne contient pas une page d'inscriptions valide.")
        for row in payload["results"]:
            if not isinstance(row, dict) or row.get("course_id") != course_key:
                raise ValueError("La réponse LMS contient une inscription hors du cours demandé.")
        results.extend(payload["results"])
        next_page = payload.get("next")
        if next_page is None:
            return results
        if not isinstance(next_page, str) or not next_page:
            raise ValueError("Le lien de pagination LMS est invalide.")
        next_url = urljoin(endpoint, next_page)
        target = urlsplit(next_url)
        if (
            (target.scheme, target.netloc, target.path) != (origin.scheme, origin.netloc, origin.path)
            or parse_qs(target.query).get("course_id") != [course_key]
            or next_url in seen
        ):
            raise ValueError("Le lien de pagination LMS ne conserve pas le périmètre demandé.")
        seen.add(next_url)
        url, params = next_url, None
