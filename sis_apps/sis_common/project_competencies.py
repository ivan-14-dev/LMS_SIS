"""Selected project objectives, never an acquisition or an official result."""

import hashlib
import json
import re
from copy import deepcopy

from django.apps import apps
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from sis_common.hierarchy import unit_path
from sis_common.institutional_profiles import validate_learning_offering
from sis_common.project_courses import course_scope_fingerprint, visible_project_courses

MAX_COMPETENCIES = 100


class CompetencyCodesField(serializers.Field):
    def to_internal_value(self, data):
        if not isinstance(data, list) or len(data) > MAX_COMPETENCIES:
            raise ValidationError("Une liste de 100 codes maximum est attendue.")
        if any(not isinstance(code, str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", code) for code in data):
            raise ValidationError("Chaque code doit respecter le format source (1 à 64 caractères), sans coercition.")
        if len(set(data)) != len(data):
            raise ValidationError("Une compétence ne peut figurer qu'une fois.")
        return data


def source_context(request, course, *, lock=False):
    """Check all local ancestry before touching the bound offering JSON."""
    tenant_id = request.tenant.pk
    dimensions = {"cours": course.pk}
    if apps.is_installed("apps.classes"):
        source = course.classe
        if lock:
            source = type(source).objects.select_for_update().get(pk=source.pk)
            course.classe = source
        tenants = (
            source.etablissement_id,
            source.niveau.etablissement_id,
            source.annee_scolaire.etablissement_id,
            course.matiere.etablissement_id,
        )
    else:
        unit = course.ecue.ue
        source = unit.maquette.formation
        if lock:
            source = type(source).objects.select_for_update().get(pk=source.pk)
            unit.maquette.formation = source
        tenants = [
            unit.maquette.annee_universitaire.universite_id,
            unit.semestre.annee_universitaire.universite_id,
        ]
        if source.departement_id:
            department = source.departement
            tenants.append(department.faculte.universite_id)
            dimensions.update(departement=department.pk, faculte=department.faculte_id)
        if source.ecole_doctorale_id:
            tenants.append(source.ecole_doctorale.universite_id)
            dimensions["ecole_doctorale"] = source.ecole_doctorale_id
    if any(value != tenant_id for value in tenants):
        raise ValidationError({"competences": "Le contexte académique du cours est hors établissement."})
    dimensions["organisation"] = [unit.pk for unit in unit_path(request.tenant, source.organisation_unit)]
    dimensions["source"] = {"model": source._meta.label_lower, "id": source.pk}
    dimensions["scope"] = course_scope_fingerprint(course)
    return source, dimensions


def competency_source(request, course):
    source, context = source_context(request, course, lock=True)
    offering = source.offre_configuration
    if offering == {} or offering is None:
        return [], "absente", context, None
    try:
        validate_learning_offering(offering)
        canonical = json.dumps(offering, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    except (DjangoValidationError, TypeError, ValueError, KeyError) as error:
        raise ValidationError(
            {"competences": "L'offre liée au cours est corrompue ; corrigez sa configuration."}
        ) from error
    reference = {
        "code": offering["code"],
        "label": offering["label"],
        "version": offering["version"],
        "_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    }
    mode = offering["assessment"]["mode"]
    criteria = offering["assessment"]["criteria"] if mode == "competency" else []
    return criteria, mode, context, reference


def select_competencies(request, course, codes, *, previous=None):
    # None means omission, [] is an explicit removal, including recovery from a revoked source.
    if codes == [] or (codes is None and previous is None):
        return None
    if course is None:
        raise ValidationError({"competences": "Choisissez un cours ou retirez explicitement les compétences visées."})
    criteria, mode, context, reference = competency_source(request, course)
    if codes is None:
        if (
            not isinstance(previous, dict)
            or previous.get("version") != 1
            or previous.get("_contexte") != context
            or previous.get("_offre") != reference
            or mode != "competency"
        ):
            raise ValidationError(
                {
                    "competences": (
                        "Le cours ou son offre a changé. " "Resélectionnez ou retirez explicitement les compétences."
                    )
                }
            )
        return previous
    by_code = {item["code"]: item for item in criteria}
    if any(code not in by_code for code in codes):
        raise ValidationError({"competences": "Une compétence choisie n'appartient pas à l'offre de ce cours."})
    return {
        "version": 1,
        "_contexte": context,
        "_offre": reference,
        "criteria": [deepcopy(by_code[code]) for code in codes],
    }


def readable_competencies(request, snapshot):
    if snapshot is None:
        return None
    hidden = {"disponible": False}
    if not isinstance(snapshot, dict) or type(snapshot.get("version")) is not int or snapshot["version"] != 1:
        return hidden
    context = snapshot.get("_contexte")
    if not isinstance(context, dict) or type(context.get("cours")) is not int:
        return hidden
    course = visible_project_courses(request, request.user).filter(pk=context["cours"]).first()
    if course is None:
        return hidden
    try:
        _, current = source_context(request, course)
        if current != context:
            return hidden
        criteria = snapshot["criteria"]
        codes = [item["code"] for item in criteria]
        CompetencyCodesField().run_validation(codes)
        if not codes or any(
            not isinstance(item["label"], str) or not 1 <= len(item["label"]) <= 240 for item in criteria
        ):
            return hidden
        return {
            "version": 1,
            "disponible": True,
            "criteria": [{"code": item["code"], "label": item["label"]} for item in criteria],
        }
    except (ValidationError, KeyError, TypeError):
        return hidden
