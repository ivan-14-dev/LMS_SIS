"""Resolve reviewed, dated configuration without rewriting existing academic records."""

from copy import deepcopy

from django.apps import apps
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Max
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from sis_common.hierarchy_models import OrganizationUnitBase
from sis_common.institutional_profiles import validate_bound_offering

OFFERING_SETTING = "learning.offering"
SETTING_SCHEMA = {
    OFFERING_SETTING: {
        "label": "Offre par défaut des nouvelles classes et formations",
        "type": "learning_offering",
        "default": None,
        "scopes": ["tenant", *[kind for kind, _label in OrganizationUnitBase.KINDS]],
        "description": "Les règles héritées sont copiées à la création, jamais réappliquées aux dossiers existants.",
    },
}


def latest_revision(tenant):
    return (
        apps.get_model("core.ConfigurationRevision")
        .objects.filter(etablissement_id=tenant.pk)
        .aggregate(latest=Max("revision"))["latest"]
        or 0
    )


def unit_path(tenant, unit):
    path, seen = [], set()
    while unit is not None:
        if unit.etablissement_id != tenant.pk or unit.pk in seen:
            raise ValidationError({"unit": "Périmètre organisationnel invalide pour cet établissement."})
        seen.add(unit.pk)
        path.append(unit)
        unit = unit.parent
    return list(reversed(path))


def validate_settings(values, locks):
    if not isinstance(values, dict) or set(values) - SETTING_SCHEMA.keys():
        raise ValidationError({"values": "La configuration contient des paramètres inconnus."})
    if not isinstance(locks, list) or any(not isinstance(key, str) for key in locks):
        raise ValidationError({"locks": "Les verrous doivent être une liste de codes de paramètres."})
    if len(set(locks)) != len(locks) or set(locks) - values.keys():
        raise ValidationError({"locks": "Un verrou unique doit porter sur une valeur définie dans ce périmètre."})
    for key, value in values.items():
        if key == OFFERING_SETTING and value is not None:
            try:
                validate_bound_offering(value)
            except DjangoValidationError as error:
                raise ValidationError({"values": error.messages}) from error


def resolve_configuration(tenant, unit=None, at=None, proposed=None, publications=None):
    at = at or timezone.now()
    path = unit_path(tenant, unit)
    scope_ids = [None, *[item.pk for item in path]]
    rows = (
        publications
        if publications is not None
        else list(
            apps.get_model("core.ConfigurationRevision")
            .objects.filter(etablissement_id=tenant.pk, effective_from__lte=at)
            .order_by("effective_from", "revision")
        )
    )
    selected = {}
    for row in rows:
        if row.unit_id in scope_ids and row.effective_from <= at:
            selected[row.unit_id] = {
                "values": row.values,
                "locks": row.locks,
                "revision": row.revision,
                "effective_from": row.effective_from.isoformat(),
            }
    if proposed is not None:
        selected[proposed["unit_id"]] = proposed
    values = {key: deepcopy(item["default"]) for key, item in SETTING_SCHEMA.items()}
    origins = {key: {"scope": "default", "unit": None, "label": "Valeur par défaut", "revision": 0} for key in values}
    locked, ignored = {}, []
    for item in [None, *path]:
        identifier = item.pk if item else None
        row = selected.get(identifier)
        if row is None:
            continue
        origin = {
            "scope": item.kind if item else "tenant",
            "unit": identifier,
            "label": str(item) if item else tenant.nom,
            "revision": row["revision"],
            "effective_from": row["effective_from"],
        }
        for key, value in row["values"].items():
            if key in locked:
                ignored.append({"key": key, "unit": identifier, "locked_by": locked[key]})
                continue
            values[key] = deepcopy(value)
            origins[key] = origin
            if key in row["locks"]:
                locked[key] = origin
    return {
        "at": at.isoformat(),
        "unit": unit.pk if unit else None,
        "path": [{"id": item.pk, "code": item.code, "nom": item.nom, "kind": item.kind} for item in path],
        "values": values,
        "origins": origins,
        "locks": locked,
        "ignored_overrides": ignored,
        "local": selected.get(unit.pk if unit else None, {"values": {}, "locks": [], "revision": 0}),
    }


def explicit_binding_origin(unit):
    return {
        "unit": unit.pk if unit else None,
        "at": timezone.now().isoformat(),
        "source": {"scope": "explicit", "unit": None, "label": "Choix explicite", "revision": 0},
        "locked": False,
        "inherited": False,
    }


def inherited_binding(tenant, unit, explicit_code):
    result = resolve_configuration(tenant, unit)
    offering = result["values"][OFFERING_SETTING]
    locked = OFFERING_SETTING in result["locks"]
    if locked and explicit_code and (offering is None or explicit_code != offering["code"]):
        raise ValidationError({"offre_code": "L'offre est verrouillée par la configuration héritée."})
    inherited = not explicit_code or (locked and offering is not None)
    if not inherited:
        return None, explicit_binding_origin(unit)
    origin = {
        "unit": result["unit"],
        "at": result["at"],
        "source": result["origins"][OFFERING_SETTING],
        "locked": locked,
        "inherited": inherited,
    }
    return deepcopy(offering), origin
