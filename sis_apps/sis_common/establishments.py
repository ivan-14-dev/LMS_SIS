from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator

FEATURE_LABELS = {
    "cours_en_ligne": "Cours en ligne",
    "partage_cours": "Partage et réutilisation de cours",
    "classes_virtuelles": "Classes virtuelles",
    "examens_ecrits": "Examens écrits",
    "qcm": "Questionnaires à choix multiple",
    "correction_automatique": "Correction automatique",
}

LIVE_PROVIDER_LABELS = {
    "none": "Désactivé",
    "bigbluebutton": "BigBlueButton",
    "zoom_lti": "Zoom LTI Pro",
    "other_lti": "Autre fournisseur LTI",
}


def default_establishment_features():
    return {
        "cours_en_ligne": True,
        "partage_cours": True,
        "classes_virtuelles": False,
        "examens_ecrits": True,
        "qcm": True,
        "correction_automatique": True,
    }


def default_live_configuration():
    return {"provider": "none", "public_url": ""}


def validate_establishment_features(value):
    if not isinstance(value, dict):
        raise ValidationError("Les fonctionnalités doivent être un objet.")

    unknown = set(value) - set(FEATURE_LABELS)
    if unknown:
        raise ValidationError(
            f"Fonctionnalités inconnues : {', '.join(sorted(unknown))}."
        )

    invalid = [key for key, enabled in value.items() if not isinstance(enabled, bool)]
    if invalid:
        raise ValidationError(
            f"Ces fonctionnalités doivent être booléennes : {', '.join(sorted(invalid))}."
        )


def validate_live_configuration(value):
    if not isinstance(value, dict):
        raise ValidationError(
            "La configuration de classe virtuelle doit être un objet."
        )

    unknown = set(value) - {"provider", "public_url"}
    if unknown:
        raise ValidationError(
            f"Champs de visioconférence inconnus : {', '.join(sorted(unknown))}."
        )

    provider = value.get("provider", "none")
    if provider not in LIVE_PROVIDER_LABELS:
        raise ValidationError(
            {"provider": "Ce fournisseur de classe virtuelle n'est pas pris en charge."}
        )

    public_url = value.get("public_url", "")
    if not isinstance(public_url, str):
        raise ValidationError(
            {"public_url": "L'URL publique doit être une chaîne de caractères."}
        )
    if not public_url:
        return

    URLValidator(schemes=["https"])(public_url)
    parsed_url = urlsplit(public_url)
    if (
        parsed_url.username
        or parsed_url.password
        or parsed_url.query
        or parsed_url.fragment
    ):
        raise ValidationError(
            {
                "public_url": (
                    "L'URL publique ne doit contenir ni identifiant, "
                    "ni paramètres, ni fragment."
                )
            }
        )


def validate_timezone(value):
    try:
        ZoneInfo(value)
    except (TypeError, ValueError, ZoneInfoNotFoundError) as exc:
        raise ValidationError("Ce fuseau horaire IANA est invalide.") from exc
