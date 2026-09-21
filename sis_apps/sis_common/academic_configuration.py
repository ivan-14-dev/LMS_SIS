"""Validation helpers for tenant-defined academic structures and rules."""

import re
from copy import deepcopy
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError

DIMENSION_AXES = {
    "institutional": "Institutionnel",
    "academic": "Académique",
    "organizational": "Organisationnel",
    "pedagogical": "Pédagogique",
    "financial": "Financier",
}

DIMENSION_SCOPES = {
    "tenant": "Établissement",
    "academic_year": "Année académique",
    "period": "Période",
    "semester": "Semestre",
    "level": "Niveau",
    "class": "Classe",
    "department": "Département",
    "program": "Filière / formation",
    "section": "Section / parcours",
    "subject": "Matière / ECUE",
    "unit": "UE / unité d'enseignement",
    "payment": "Rubrique de paiement",
}

VALIDATION_POLICY_SCOPES = {
    "tenant": "Établissement",
    "academic_year": "Année académique",
    "level": "Niveau",
    "class": "Classe",
    "formation": "Formation",
    "semester": "Semestre",
}

REPORT_DATASET_LABELS = {
    "notes": "Notes",
    "evaluations": "Évaluations",
    "bulletins": "Bulletins",
    "financial_invoices": "Factures",
    "financial_payments": "Paiements",
}

FINANCIAL_WORKFLOW_SCOPES = {
    "tenant": "Établissement",
    "academic_year": "Année académique",
    "payment_rubric": "Rubrique de paiement",
}

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
    "dimensions": [
        {
            "code": "institution_type",
            "label": "Type d'établissement",
            "axis": "institutional",
            "scope": "tenant",
            "applicable_to": ["secondaire", "superieur"],
        },
        {
            "code": "academic_year",
            "label": "Année académique",
            "axis": "academic",
            "scope": "academic_year",
            "applicable_to": ["secondaire", "superieur"],
        },
        {
            "code": "period",
            "label": "Période",
            "axis": "academic",
            "scope": "period",
            "applicable_to": ["secondaire", "superieur"],
        },
        {
            "code": "semester",
            "label": "Semestre",
            "axis": "academic",
            "scope": "semester",
            "applicable_to": ["superieur"],
        },
        {
            "code": "level",
            "label": "Niveau",
            "axis": "academic",
            "scope": "level",
            "applicable_to": ["secondaire", "superieur"],
        },
        {
            "code": "class",
            "label": "Classe",
            "axis": "organizational",
            "scope": "class",
            "applicable_to": ["secondaire"],
        },
        {
            "code": "department",
            "label": "Département",
            "axis": "organizational",
            "scope": "department",
            "applicable_to": ["superieur"],
        },
        {
            "code": "program",
            "label": "Filière / formation",
            "axis": "organizational",
            "scope": "program",
            "applicable_to": ["superieur"],
        },
        {
            "code": "subject",
            "label": "Matière / ECUE",
            "axis": "pedagogical",
            "scope": "subject",
            "applicable_to": ["secondaire", "superieur"],
        },
        {
            "code": "teaching_unit",
            "label": "UE / unité d'enseignement",
            "axis": "pedagogical",
            "scope": "unit",
            "applicable_to": ["superieur"],
        },
        {
            "code": "payment_rubric",
            "label": "Rubrique de paiement",
            "axis": "financial",
            "scope": "payment",
            "applicable_to": ["secondaire", "superieur"],
        },
    ],
    "custom_dimensions": [],
    "permission_groups": [
        {
            "code": "academic_admin_secondary",
            "label": "Administration pédagogique secondaire",
            "permissions": [
                "notes.change_reglevalidation",
                "utilisateurs.view_utilisateur",
                "etablissement.change_etablissement",
            ],
            "attributes": {},
        },
        {
            "code": "academic_admin_superieur",
            "label": "Administration pédagogique supérieur",
            "permissions": [
                "notes.change_reglevalidation",
                "utilisateurs.view_utilisateur",
                "etablissement.change_universite",
            ],
            "attributes": {},
        },
        {
            "code": "finance_manager_secondary",
            "label": "Gestion financière secondaire",
            "permissions": [
                "paiements.change_paiement",
            ],
            "attributes": {},
        },
        {
            "code": "finance_manager_superieur",
            "label": "Gestion financière supérieur",
            "permissions": [
                "paiements.change_paiementfrais",
            ],
            "attributes": {},
        },
        {
            "code": "academic_registry_superieur",
            "label": "Scolarité et registres supérieur",
            "permissions": [
                "releves.change_relevenotes",
                "releves.change_transcript",
                "releves.change_attestation",
            ],
            "attributes": {},
        },
        {
            "code": "document_signatory_superieur",
            "label": "Signataire documentaire supérieur",
            "permissions": [
                "releves.change_relevenotes",
                "releves.change_transcript",
                "releves.change_attestation",
                "diplomes.change_cessiondiplome",
            ],
            "attributes": {},
        },
        {
            "code": "exam_manager_secondary",
            "label": "Gestion examens secondaire",
            "permissions": [
                "examens.change_sessionexamen",
                "examens.change_epreuveexamen",
                "examens.change_convocationexamen",
                "examens.change_resultatexamen",
            ],
            "attributes": {},
        },
        {
            "code": "exam_manager_superieur",
            "label": "Gestion examens supérieur",
            "permissions": [
                "examens.change_sessionexamen",
                "examens.change_epreuveexamen",
                "examens.change_convocationexamen",
            ],
            "attributes": {},
        },
        {
            "code": "registration_manager_superieur",
            "label": "Gestion inscriptions supérieur",
            "permissions": [
                "etudiants.change_inscriptionadministrative",
            ],
            "attributes": {},
        },
        {
            "code": "stage_manager_secondary",
            "label": "Gestion stages secondaire",
            "permissions": [
                "stages.change_conventionstage",
                "stages.change_entreprise",
                "stages.change_suivistage",
                "stages.change_evaluationstage",
            ],
            "attributes": {},
        },
        {
            "code": "jury_manager_superieur",
            "label": "Gestion jurys supérieur",
            "permissions": [
                "jurys.change_jury",
                "jurys.change_deliberation",
                "jurys.change_decisionjury",
                "jurys.change_decisionglobale",
            ],
            "attributes": {},
        },
        {
            "code": "class_council_manager_secondary",
            "label": "Gestion conseils de classe secondaire",
            "permissions": [
                "conseil_classe.change_conseilclasse",
                "conseil_classe.change_decisionconseil",
                "conseil_classe.change_appreciationconseil",
            ],
            "attributes": {},
        },
        {
            "code": "attendance_manager_secondary",
            "label": "Gestion présences secondaire",
            "permissions": [
                "presences.change_appel",
                "presences.change_presence",
                "presences.change_justificatif",
            ],
            "attributes": {},
        },
        {
            "code": "memoire_manager_superieur",
            "label": "Gestion mémoires supérieur",
            "permissions": [
                "memoires.change_sujetmemoire",
                "memoires.change_memoire",
                "memoires.change_jurymemoire",
            ],
            "attributes": {},
        },
        {
            "code": "class_manager_secondary",
            "label": "Gestion classes secondaire",
            "permissions": [
                "classes.change_classe",
                "classes.change_groupe",
                "classes.change_matiere",
                "classes.change_programmematiere",
            ],
            "attributes": {},
        },
        {
            "code": "student_manager_secondary",
            "label": "Gestion élèves secondaire",
            "permissions": [
                "eleves.change_eleve",
                "eleves.change_inscription",
                "eleves.change_tuteur",
                "eleves.change_elevetuteur",
            ],
            "attributes": {},
        },
        {
            "code": "schedule_manager_secondary",
            "label": "Gestion emplois du temps secondaire",
            "permissions": [
                "emplois_du_temps.change_creneau",
                "emplois_du_temps.change_contrainte",
            ],
            "attributes": {},
        },
        {
            "code": "student_manager_superieur",
            "label": "Gestion étudiants supérieur",
            "permissions": [
                "etudiants.change_etudiant",
                "etudiants.change_inscriptionadministrative",
            ],
            "attributes": {},
        },
        {
            "code": "mobility_manager_superieur",
            "label": "Gestion mobilité supérieur",
            "permissions": [
                "mobilite.change_programmemobilite",
                "mobilite.change_candidaturemobilite",
                "mobilite.change_accordetudes",
            ],
            "attributes": {},
        },
        {
            "code": "retake_manager_superieur",
            "label": "Gestion rattrapages supérieur",
            "permissions": [
                "rattrapages.change_inscriptionrattrapage",
            ],
            "attributes": {},
        },
    ],
    "validation_policies": [],
    "financial_workflows": [
        {
            "code": "payment_review",
            "label": "Validation des paiements",
            "scope": "tenant",
            "steps": [
                {"code": "submitted", "label": "Soumis"},
                {"code": "under_review", "label": "En contrôle"},
                {"code": "validated", "label": "Validé", "terminal": True},
                {"code": "rejected", "label": "Rejeté", "terminal": True},
                {"code": "refunded", "label": "Remboursé", "terminal": True},
            ],
            "required_permissions": ["paiements.change_paiement", "paiements.change_paiementfrais"],
            "transitions": [
                {"action": "valider", "from": "en_attente", "to": "valide"},
                {"action": "rejeter", "from": "en_attente", "to": "rejete"},
                {"action": "rembourser", "from": "valide", "to": "rembourse"},
            ],
        }
    ],
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


def _validate_string_list(items, path, *, empty_allowed=True):
    if not isinstance(items, list):
        raise ValidationError(f"{path} doit être une liste.")
    if not empty_allowed and not items:
        raise ValidationError(f"{path} ne peut pas être vide.")
    for index, item in enumerate(items):
        if not isinstance(item, str) or not item.strip():
            raise ValidationError(f"{path}[{index}] doit être une chaîne non vide.")


def _validate_targets(value, path):
    if not isinstance(value, dict):
        raise ValidationError(f"{path} doit être un objet.")
    for key, target in value.items():
        if not re.fullmatch(r"[a-z][a-z0-9_]{1,63}", key):
            raise ValidationError(f"{path}.{key} est invalide.")
        if isinstance(target, list):
            if not target:
                raise ValidationError(f"{path}.{key} ne peut pas être vide.")
        elif isinstance(target, (str, int, float, bool)) or target is None:
            continue
        else:
            raise ValidationError(f"{path}.{key} doit être scalaire ou une liste.")


def _validate_dimensions(items):
    _validate_code_items(items, "dimensions")
    for index, item in enumerate(items):
        axis = item.get("axis")
        scope = item.get("scope")
        if axis not in DIMENSION_AXES:
            raise ValidationError(f"dimensions[{index}].axis est invalide.")
        if scope not in DIMENSION_SCOPES:
            raise ValidationError(f"dimensions[{index}].scope est invalide.")
        applicable_to = item.get("applicable_to", [])
        _validate_string_list(applicable_to, f"dimensions[{index}].applicable_to")


def _validate_permission_groups(items):
    _validate_code_items(items, "permission_groups")
    for index, item in enumerate(items):
        _validate_string_list(
            item.get("permissions", []),
            f"permission_groups[{index}].permissions",
            empty_allowed=False,
        )
        attributes = item.get("attributes", {})
        if not isinstance(attributes, dict):
            raise ValidationError(f"permission_groups[{index}].attributes doit être un objet.")


def _validate_validation_policies(items):
    _validate_code_items(items, "validation_policies")
    for index, item in enumerate(items):
        scope = item.get("scope")
        if scope not in VALIDATION_POLICY_SCOPES:
            raise ValidationError(f"validation_policies[{index}].scope est invalide.")
        if "targets" in item:
            _validate_targets(item["targets"], f"validation_policies[{index}].targets")
        if "criteria" in item:
            validate_rule_criteria(item["criteria"])
        thresholds = item.get("thresholds", {})
        if not isinstance(thresholds, dict):
            raise ValidationError(f"validation_policies[{index}].thresholds doit être un objet.")
        for name, threshold in thresholds.items():
            if isinstance(threshold, bool):
                continue
            _decimal(threshold, f"validation_policies[{index}].thresholds.{name}")
        publication = item.get("publication", {})
        if not isinstance(publication, dict):
            raise ValidationError(f"validation_policies[{index}].publication doit être un objet.")
        for key in ("requires_financial_clearance", "auto_publish", "manual_review_required"):
            if key in publication and not isinstance(publication[key], bool):
                raise ValidationError(f"validation_policies[{index}].publication.{key} doit être booléen.")


def _validate_financial_workflows(items):
    _validate_code_items(items, "financial_workflows")
    for index, workflow in enumerate(items):
        scope = workflow.get("scope")
        if scope not in FINANCIAL_WORKFLOW_SCOPES:
            raise ValidationError(f"financial_workflows[{index}].scope est invalide.")
        if "targets" in workflow:
            _validate_targets(workflow["targets"], f"financial_workflows[{index}].targets")
        _validate_string_list(
            workflow.get("required_permissions", []),
            f"financial_workflows[{index}].required_permissions",
        )
        steps = workflow.get("steps", [])
        _validate_code_items(steps, f"financial_workflows[{index}].steps")
        for step_index, step in enumerate(steps):
            if "terminal" in step and not isinstance(step["terminal"], bool):
                raise ValidationError(
                    f"financial_workflows[{index}].steps[{step_index}].terminal doit être booléen."
                )
        transitions = workflow.get("transitions", [])
        if not isinstance(transitions, list):
            raise ValidationError(f"financial_workflows[{index}].transitions doit être une liste.")
        for transition_index, transition in enumerate(transitions):
            if not isinstance(transition, dict):
                raise ValidationError(
                    f"financial_workflows[{index}].transitions[{transition_index}] doit être un objet."
                )
            for key in ("action", "from", "to"):
                value = str(transition.get(key, "")).strip()
                if not value:
                    raise ValidationError(
                        f"financial_workflows[{index}].transitions[{transition_index}].{key} est requis."
                    )


def _validate_reports(items):
    _validate_code_items(items, "reports")
    for index, report in enumerate(items):
        dataset = report.get("dataset")
        if dataset not in REPORT_DATASET_LABELS:
            raise ValidationError(
                f"reports[{index}].dataset doit être l'un de: {', '.join(sorted(REPORT_DATASET_LABELS))}."
            )
        if not isinstance(report.get("fields"), list) or not report["fields"]:
            raise ValidationError(f"reports[{index}].fields doit être une liste non vide.")
        if not isinstance(report.get("allowed_filters", []), list):
            raise ValidationError(f"reports[{index}].allowed_filters doit être une liste.")
        if "required_permissions" in report:
            _validate_string_list(
                report["required_permissions"],
                f"reports[{index}].required_permissions",
                empty_allowed=False,
            )
        default_group_by = report.get("default_group_by")
        if default_group_by is not None and (not isinstance(default_group_by, str) or not default_group_by.strip()):
            raise ValidationError(f"reports[{index}].default_group_by doit être une chaîne non vide.")


def academic_configuration_schema():
    return {
        "dimension_axes": [{"code": code, "label": label} for code, label in DIMENSION_AXES.items()],
        "dimension_scopes": [{"code": code, "label": label} for code, label in DIMENSION_SCOPES.items()],
        "validation_scopes": [{"code": code, "label": label} for code, label in VALIDATION_POLICY_SCOPES.items()],
        "report_datasets": [{"code": code, "label": label} for code, label in REPORT_DATASET_LABELS.items()],
        "financial_workflow_scopes": [
            {"code": code, "label": label} for code, label in FINANCIAL_WORKFLOW_SCOPES.items()
        ],
    }


def _target_matches(targets, context):
    context = context or {}
    for key, expected in (targets or {}).items():
        actual = context.get(key)
        if isinstance(expected, list):
            if actual not in expected:
                return False
        elif actual != expected:
            return False
    return True


def resolve_validation_policy(configuration, candidates):
    policies = (configuration or {}).get("validation_policies", [])
    candidates = candidates if isinstance(candidates, list) else [candidates]
    for candidate in candidates:
        scope = candidate.get("scope")
        context = candidate.get("context", {})
        matching = [
            policy
            for policy in policies
            if policy.get("scope") == scope
            and policy.get("active", True)
            and _target_matches(policy.get("targets", {}), context)
        ]
        if matching:
            return sorted(
                matching,
                key=lambda item: (-len(item.get("targets", {})), item.get("priority", 100)),
            )[0]
    return None


def resolve_financial_workflow(configuration, candidates):
    workflows = (configuration or {}).get("financial_workflows", [])
    candidates = candidates if isinstance(candidates, list) else [candidates]
    for candidate in candidates:
        scope = candidate.get("scope")
        context = candidate.get("context", {})
        matching = [
            workflow
            for workflow in workflows
            if workflow.get("scope") == scope
            and workflow.get("active", True)
            and _target_matches(workflow.get("targets", {}), context)
        ]
        if matching:
            return sorted(
                matching,
                key=lambda item: (-len(item.get("targets", {})), item.get("priority", 100)),
            )[0]
    return None


def workflow_transition_allowed(workflow, action, current_status, next_status):
    transitions = (workflow or {}).get("transitions", [])
    if not transitions:
        return True
    return any(
        transition.get("action") == action
        and transition.get("from") == current_status
        and transition.get("to") == next_status
        for transition in transitions
    )


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
    _validate_dimensions(value.get("dimensions", []))
    _validate_code_items(value.get("custom_dimensions", []), "custom_dimensions")
    _validate_permission_groups(value.get("permission_groups", []))
    _validate_validation_policies(value.get("validation_policies", []))
    _validate_financial_workflows(value.get("financial_workflows", []))
    _validate_reports(value.get("reports", []))


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
