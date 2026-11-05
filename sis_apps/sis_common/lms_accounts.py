"""Account provisioning contract for the explicitly installed LMS extension."""

import re
from urllib.parse import quote

import requests


def provision_account(client, username, email, full_name, *, user_id=None):
    if not isinstance(username, str) or not re.fullmatch(r"[\w-]{2,30}", username):
        raise ValueError("Identifiant de compte LMS invalide.")
    if not isinstance(email, str) or not isinstance(full_name, str):
        raise ValueError("Le nom et l'adresse du compte LMS doivent être renseignés.")
    if user_id is not None and (type(user_id) is not int or user_id <= 0):
        raise ValueError("Identifiant numérique LMS invalide.")
    data = {"email": email.strip(), "name": full_name.strip()}
    operation = requests.post
    if user_id is not None:
        operation = requests.patch
        data["id"] = user_id
    response = operation(
        f"{client.lms_url}/api/sis/v1/accounts/{quote(username, safe='')}/",
        json=data,
        headers=client._headers(),
        timeout=client.timeout,
        verify=client.verify_ssl,
        allow_redirects=False,
    )
    response.raise_for_status()
    if response.status_code not in (200, 201):
        raise ValueError("Le LMS ne confirme pas le provisioning du compte.")
    result = response.json()
    if (
        not isinstance(result, dict)
        or type(result.get("id")) is not int
        or result["id"] <= 0
        or (user_id is not None and result["id"] != user_id)
        or result.get("username") != username
        or result.get("email") != data["email"]
        or result.get("name") != data["name"]
        or result.get("is_active") is not True
        or result.get("is_staff") is not False
        or result.get("is_superuser") is not False
    ):
        raise ValueError("La réponse LMS ne confirme pas l'identité et les droits du compte demandé.")
    return result


def create_account(client, username, email, full_name, *, is_staff, is_superuser, role, extra):
    if is_staff is not False or is_superuser is not False or extra or role not in ("student", "teacher"):
        raise ValueError("Les privilèges globaux et champs supplémentaires ne sont pas provisionnés par le SIS.")
    return provision_account(client, username, email, full_name)


def update_account(client, username, data, *, user_id):
    if not isinstance(data, dict) or set(data) != {"email", "name"}:
        raise ValueError("Seuls le nom et l'adresse du compte LMS sont modifiables.")
    return provision_account(client, username, data["email"], data["name"], user_id=user_id)
