"""Validation helpers for tenant-defined academic structures and rules."""

import re
from copy import deepcopy
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError

DEFAULT_ACADEMIC_CONFIGURATION = {
    "language": "fr",
    "framework": "custom",
    "grading_scale": {"minimum": 0, "maximum": 20, "pass_mark": 10},
    "evaluation_types": [
        {"code": "controle", "label": "Contrôle continu"},
        {"code": "composition", "label": "Composition"},
        {"code": "examen", "label": "Examen"},
    ],
    "catalogs": {
        "institution_types": [],
        "period_types": [],
        "group_types": [],
        "subject_types": [],
        "formation_types": [],
        "formation_levels": [],
        "study_regimes": [],
        "teaching_modalities": [],
        "ue_types": [],
    },
    "custom_dimensions": [],
    "reports": [],
}


def default_academic_configuration():
    return deepcopy(DEFAULT_ACADEMIC_CONFIGURATION)


def _decimal(value, path):
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationError(f"{path} doit être un nombre.") from exc


def _validate_code_items(items, path):
    if not isinstance(items, list):
        raise ValidationError(f"{path} doit être une liste.")
    codes = set()
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValidationError(f"{path}[{index}] doit être un objet.")
        code = str(item.get("code", "")).strip()
        label = str(item.get("label", "")).strip()
        if not code or not label:
            raise ValidationError(f"{path}[{index}] exige code et label.")
        if code in codes:
            raise ValidationError(f"Le code {code!r} est dupliqué dans {path}.")
        codes.add(code)


def validate_academic_configuration(value):
    if not isinstance(value, dict):
        raise ValidationError("La configuration académique doit être un objet.")
    unknown = set(value) - set(DEFAULT_ACADEMIC_CONFIGURATION)
    if unknown:
        raise ValidationError(f"Clés de configuration académique inconnues: {', '.join(sorted(unknown))}.")

    scale = value.get("grading_scale", {})
    if not isinstance(scale, dict):
        raise ValidationError("grading_scale doit être un objet.")
    required = {"minimum", "maximum", "pass_mark"}
    if set(scale) != required:
        raise ValidationError("grading_scale exige uniquement minimum, maximum et pass_mark.")
    minimum = _decimal(scale["minimum"], "grading_scale.minimum")
    maximum = _decimal(scale["maximum"], "grading_scale.maximum")
    pass_mark = _decimal(scale["pass_mark"], "grading_scale.pass_mark")
    if minimum >= maximum or not minimum <= pass_mark <= maximum:
        raise ValidationError("L'échelle de notation ou le seuil de réussite est invalide.")

    _validate_code_items(value.get("evaluation_types", []), "evaluation_types")
    catalogs = value.get("catalogs", {})
    if not isinstance(catalogs, dict):
        raise ValidationError("catalogs doit être un objet.")
    for name, items in catalogs.items():
        if not re.fullmatch(r"[a-z][a-z0-9_]{1,63}", name):
            raise ValidationError(f"Nom de catalogue invalide: {name!r}.")
        _validate_code_items(items, f"catalogs.{name}")
    _validate_code_items(value.get("custom_dimensions", []), "custom_dimensions")
    reports = value.get("reports", [])
    _validate_code_items(reports, "reports")
    for index, report in enumerate(reports):
        if report.get("dataset") != "notes":
            raise ValidationError(f"reports[{index}].dataset doit être « notes ».")
        if not isinstance(report.get("fields"), list) or not report["fields"]:
            raise ValidationError(f"reports[{index}].fields doit être une liste non vide.")
        if not isinstance(report.get("allowed_filters", []), list):
            raise ValidationError(f"reports[{index}].allowed_filters doit être une liste.")


def merge_academic_configuration(current, updates):
    merged = default_academic_configuration()
    merged.update(current or {})
    merged.update(updates or {})
    if "grading_scale" in updates:
        merged["grading_scale"] = {
            **DEFAULT_ACADEMIC_CONFIGURATION["grading_scale"],
            **(current or {}).get("grading_scale", {}),
            **updates["grading_scale"],
        }
    if "catalogs" in updates:
        merged["catalogs"] = {
            **DEFAULT_ACADEMIC_CONFIGURATION["catalogs"],
            **(current or {}).get("catalogs", {}),
            **updates["catalogs"],
        }
    validate_academic_configuration(merged)
    return merged


def catalog_options(configuration, name, fallback=()):
    items = (configuration or {}).get("catalogs", {}).get(name, [])
    if items:
        return deepcopy(items)
    return [{"code": code, "label": label} for code, label in fallback]


def catalog_label(configuration, name, code, fallback=()):
    options = catalog_options(configuration, name, fallback)
    return next(
        (item["label"] for item in options if item["code"] == code),
        code,
    )


def validate_rule_criteria(value):
    if not isinstance(value, dict):
        raise ValidationError("Les critères doivent être un objet.")
    for code, criterion in value.items():
        if not re.fullmatch(r"[a-z][a-z0-9_]{1,63}", code):
            raise ValidationError(f"Code de critère invalide: {code!r}.")
        if not isinstance(criterion, dict):
            raise ValidationError(f"Le critère {code!r} doit être un objet.")
        operator = criterion.get("operator")
        if operator not in {"gte", "lte", "eq", "in"}:
            raise ValidationError(f"Opérateur invalide pour le critère {code!r}.")
        if "value" not in criterion:
            raise ValidationError(f"Le critère {code!r} exige une valeur.")
        if operator == "in" and not isinstance(criterion["value"], list):
            raise ValidationError(f"La valeur du critère {code!r} doit être une liste.")


def evaluate_rule_criteria(criteria, data):
    validate_rule_criteria(criteria)
    data = data or {}
    failures = []
    for code, criterion in criteria.items():
        actual = data.get(code)
        expected = criterion["value"]
        operator = criterion["operator"]
        passed = False
        if actual is not None:
            if operator == "in":
                passed = actual in expected
            elif operator == "eq":
                passed = actual == expected
            else:
                try:
                    actual_number = _decimal(actual, code)
                    expected_number = _decimal(expected, code)
                    passed = actual_number >= expected_number if operator == "gte" else actual_number <= expected_number
                except ValidationError:
                    passed = False
        if not passed:
            failures.append(f"critere:{code}")
    return failures
