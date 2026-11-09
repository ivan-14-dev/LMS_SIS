"""Pure practical-training rules, independent of either SIS and its ORM."""

import hashlib
import json
import re
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

PERMISSIONS = {
    "manage": "stages.gerer_suivi_pratique",
    "consult": "stages.consulter_suivi_pratique",
    "enter": "stages.saisir_heures_pratiques",
    "validate": "stages.valider_heures_pratiques",
    "evaluate": "stages.evaluer_competences_pratiques",
}
SCOPE_KEYS = {"etablissement_id", "programme_id", "dossier_id"}
LIVE_STATES = ("brouillon", "soumise", "validee")
CODE_PATTERN = r"[a-z][a-z0-9_-]{0,63}"


class PracticalRuleError(ValueError):
    def __init__(self, detail, code="validation_error", field=None, status=400):
        super().__init__(detail)
        self.code, self.field, self.status = code, field, status


def canonical_hash(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()


def constraints(attributes, permission):
    if not isinstance(attributes, dict):
        return None
    scopes = attributes.get("permission_scopes", {})
    if not isinstance(scopes, dict):
        return None
    result = scopes.get(permission, {})
    if not isinstance(result, dict):
        return None
    for key, values in result.items():
        if key not in SCOPE_KEYS or not isinstance(values, list) or not values:
            return None
        if any(type(value) is not int or value <= 0 for value in values):
            return None
    return result


def minute(value, *, end=False):
    if end and value == "24:00":
        return 1440
    if not isinstance(value, str) or not re.fullmatch(r"(?:[01][0-9]|2[0-3]):[0-5][0-9]", value):
        raise PracticalRuleError("Une heure HH:MM est requise.", "horaire_incoherent")
    hours, minutes = map(int, value.split(":"))
    return hours * 60 + minutes


def clock(value):
    return f"{value // 60:02d}:{value % 60:02d}"


def wall_interval(day, start, end, pause, zone_name, now, first, last):
    left, right = minute(start), minute(end, end=True)
    if right <= left or type(pause) is not int or not 0 <= pause < right - left:
        raise PracticalRuleError("Horaires ou pause incohérents.", "horaire_incoherent", "pause_minutes")
    if not first <= day <= last:
        raise PracticalRuleError("La date est hors convention.", "hors_periode", "date")
    try:
        zone = ZoneInfo(zone_name)
    except (ZoneInfoNotFoundError, TypeError, ValueError) as error:
        raise PracticalRuleError("Fuseau institutionnel invalide.", "horaire_incoherent") from error
    baseline = datetime.combine(day, time.min)
    offset = None
    finish = None
    # Minute precision is bounded to one day. Check every covered label and the
    # exclusive end: make_aware alone silently accepts nonexistent/folded labels.
    for index in range(left, right + 1):
        local = baseline + timedelta(minutes=index)
        alternatives = []
        for fold in (0, 1):
            instant = local.replace(tzinfo=zone, fold=fold)
            if instant.astimezone(UTC).astimezone(zone).replace(tzinfo=None) == local:
                alternatives.append(instant)
        if not alternatives or len({item.utcoffset() for item in alternatives}) != 1:
            raise PracticalRuleError("Scindez le travail hors transition horaire.", "transition_horaire")
        instant = alternatives[0]
        if offset is not None and instant.utcoffset() != offset:
            raise PracticalRuleError("Scindez le travail hors transition horaire.", "transition_horaire")
        offset, finish = instant.utcoffset(), instant
    if finish.astimezone(UTC) > now.astimezone(UTC):
        raise PracticalRuleError("Le travail ne peut être futur.", "travail_futur", "heure_fin")
    return left, right, right - left - pause


def criteria(value, *, published=False):
    if not isinstance(value, list) or len(value) > 100 or (published and not value):
        raise PracticalRuleError("Définissez de 1 à 100 compétences à publier.", field="competences")
    seen = set()
    for item in value:
        if not isinstance(item, dict) or set(item) != {"code", "label"}:
            raise PracticalRuleError("Une compétence attend code et label.", field="competences")
        code, label = item["code"], item["label"]
        if (
            not isinstance(code, str)
            or not re.fullmatch(CODE_PATTERN, code)
            or code in seen
            or not isinstance(label, str)
            or not 1 <= len(label) <= 240
            or label != label.strip()
        ):
            raise PracticalRuleError("Code unique et libellé non vide requis.", field="competences")
        seen.add(code)
    return value
