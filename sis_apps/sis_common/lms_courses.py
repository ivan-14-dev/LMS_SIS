"""Owned Studio course provisioning, with strict remote confirmations."""

import re
from datetime import datetime
from urllib.parse import quote
from uuid import UUID

import requests
from django.utils import timezone
from django.utils.dateparse import parse_datetime


def course_sync_requested_at(value=None):
    if value is None:
        return timezone.now()
    if isinstance(value, str):
        value = parse_datetime(value)
    if not isinstance(value, datetime) or timezone.is_naive(value):
        raise ValueError("La date de la demande de synchronisation doit inclure un fuseau.")
    return value


def course_parts(course_key):
    if not isinstance(course_key, str) or len(course_key) > 200:
        raise ValueError("Identifiant de cours LMS invalide.")
    match = re.fullmatch(r"course-v1:([\w.-]+)\+([\w.-]+)\+([\w.-]+)", course_key)
    if match is None:
        raise ValueError("Un identifiant course-v1 canonique est requis.")
    return match.groups()


def _request(client, operation, course_key, data=None):
    course_parts(course_key)
    arguments = {}
    if data is not None:
        if not isinstance(data, dict) or set(data) != {"display_name"}:
            raise ValueError("Seul le nom du cours est modifiable par ce contrat.")
        name = data["display_name"]
        if not isinstance(name, str) or not name.strip() or len(name.strip()) > 300:
            raise ValueError("Le nom du cours doit contenir entre 1 et 300 caractères.")
        arguments["json"] = {"display_name": name.strip()}
    arguments.update(
        headers=client._headers(),
        timeout=client.timeout,
        verify=client.verify_ssl,
        allow_redirects=False,
    )
    response = operation(
        f"{client.cms_url}/api/sis/v1/courses/{quote(course_key, safe=':+')}/",
        **arguments,
    )
    if operation is requests.get and response.status_code == 404:
        return None
    response.raise_for_status()
    if response.status_code not in (200, 201):
        raise ValueError("Studio ne confirme pas le provisioning du cours.")
    result = response.json()
    if (
        not isinstance(result, dict)
        or result.get("id") != course_key
        or not isinstance(result.get("display_name"), str)
        or not result["display_name"].strip()
        or (data is not None and result["display_name"] != arguments["json"]["display_name"])
    ):
        raise ValueError("La réponse Studio ne confirme pas l'identité et le nom du cours demandé.")
    return result


def create_course(client, org, number, run, display_name, course_data=None):
    if not all(isinstance(value, str) for value in (org, number, run)):
        raise ValueError("Les composantes de l'identifiant du cours doivent être du texte.")
    if course_data is not None and course_data != {}:
        raise ValueError("Les métadonnées supplémentaires nécessitent un contrat Studio distinct.")
    return _request(client, requests.post, f"course-v1:{org}+{number}+{run}", {"display_name": display_name})


def get_course(client, course_key):
    return _request(client, requests.get, course_key)


def update_course(client, course_key, data):
    return _request(client, requests.patch, course_key, data)


def _is_revision(value):
    return isinstance(value, str) and re.fullmatch(r"[a-f0-9]{24}", value) is not None


def _publication_request(client, course_key, data=None):
    course_parts(course_key)
    if not client.cms_url:
        raise ValueError("L'URL de Studio doit être configurée.")
    arguments = {
        "headers": client._headers(),
        "timeout": client.timeout,
        "verify": client.verify_ssl,
        "allow_redirects": False,
    }
    if data is not None:
        arguments["json"] = data
    response = (requests.get if data is None else requests.post)(
        f"{client.cms_url}/api/sis/v1/courses/{quote(course_key, safe=':+')}/publication/",
        **arguments,
    )
    response.raise_for_status()
    if response.status_code != 200:
        raise ValueError("Studio ne confirme pas la révision du cours.")
    result = response.json()
    if not isinstance(result, dict) or result.get("id") != course_key or not _is_revision(result.get("revision")):
        raise ValueError("La réponse Studio ne confirme pas l'identité et la révision du cours.")
    if data is not None and (
        result.get("operation_id") != data["operation_id"]
        or result["revision"] != data["expected_revision"]
        or not _is_revision(result.get("published_version"))
    ):
        raise ValueError("La réponse Studio ne confirme pas la publication demandée.")
    return result


def get_course_revision(client, course_key):
    return _publication_request(client, course_key)


def publish_course(client, course_key, *, expected_revision, operation_id, confirm):
    if confirm is not True or not _is_revision(expected_revision):
        raise ValueError("Confirmez explicitement la révision exacte examinée dans Studio.")
    if not isinstance(operation_id, (str, UUID)):
        raise ValueError("Un identifiant UUID d'opération est requis.")
    operation_id = str(UUID(str(operation_id)))
    return _publication_request(
        client,
        course_key,
        {"operation_id": operation_id, "expected_revision": expected_revision, "confirm": True},
    )
