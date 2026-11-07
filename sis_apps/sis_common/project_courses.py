"""Local course references; never provision a course or grant any access."""

import hashlib
import json
from types import SimpleNamespace

from django.apps import apps
from rest_framework.exceptions import PermissionDenied, ValidationError

from sis_common.pagination import SISPagination

COURSE_PERMISSION = "integration.view_edxcoursemapping"
_FINGERPRINT = "_scope_fingerprint"


class ProjectCoursePagination(SISPagination):
    page_size = 20
    max_page_size = 50


def visible_project_courses(request, user):
    # Keep the native LMS course boundary, including its staff prerequisite.
    # Unlike that legacy API, a project reference also requires an explicit grant.
    from apps.integration.api import visible_course_mappings
    from apps.integration.models import EdxCourseMapping

    empty = EdxCourseMapping.objects.none()
    if not user.is_active or user.etablissement_id != request.tenant.pk or not user.has_perm(COURSE_PERMISSION):
        return empty
    scopes = (user.attributs_acces or {}).get("permission_scopes", {}).get(COURSE_PERMISSION, {})
    keys = (
        {"cours", "classes", "matieres", "annees"}
        if apps.is_installed("apps.classes")
        else {"cours", "ecues", "formations", "annees"}
    )
    if not user.is_superuser and (
        not isinstance(scopes, dict)
        or any(
            key not in keys or not isinstance(values, list) or any(type(value) is not int for value in values)
            for key, values in scopes.items()
        )
    ):
        return empty
    try:
        return visible_course_mappings(SimpleNamespace(tenant=request.tenant, user=user)).filter(actif=True)
    except PermissionDenied:
        return empty


def selectable_project_courses(request, owner):
    return visible_project_courses(request, request.user).filter(
        pk__in=visible_project_courses(request, owner).values("pk")
    )


def validate_project_course(request, owner, course_id):
    from apps.integration.models import EdxCourseMapping

    if course_id is None:
        return None
    eligible = selectable_project_courses(request, owner)
    message = {"cours": "Cours indisponible ou incompatible avec les accès du gestionnaire et du responsable."}
    if not eligible.filter(pk=course_id).exists():
        raise ValidationError(message)
    course = EdxCourseMapping.objects.select_for_update().filter(pk=course_id).first()
    if course is None or not selectable_project_courses(request, owner).filter(pk=course_id).exists():
        raise ValidationError(message)
    return course


def course_summary(course):
    if course is None:
        return None
    if apps.is_installed("apps.classes"):
        context = {
            "classe": {"id": course.classe_id, "nom": course.classe.nom},
            "matiere": {"id": course.matiere_id, "nom": course.matiere.nom},
        }
    else:
        context = {"ecue": {"id": course.ecue_id, "code": course.ecue.code, "nom": course.ecue.nom}}
    return {"id": course.pk, "nom": course.course_name, "contexte": context}


def course_scope_fingerprint(course):
    # Names are deliberately excluded: renaming within the same scope preserves history.
    if apps.is_installed("apps.classes"):
        classroom = course.classe
        dimensions = {
            "variant": "secondaire",
            "cours_id": course.pk,
            "matiere_id": course.matiere_id,
            "matiere_etablissement_id": course.matiere.etablissement_id,
            "classe_id": course.classe_id,
            "classe_etablissement_id": classroom.etablissement_id,
            "niveau_id": classroom.niveau_id,
            "niveau_etablissement_id": classroom.niveau.etablissement_id,
            "annee_scolaire_id": classroom.annee_scolaire_id,
            "annee_etablissement_id": classroom.annee_scolaire.etablissement_id,
        }
    else:
        unit = course.ecue.ue
        curriculum, semester = unit.maquette, unit.semestre
        dimensions = {
            "variant": "superieur",
            "cours_id": course.pk,
            "ecue_id": course.ecue_id,
            "ue_id": course.ecue.ue_id,
            "maquette_id": unit.maquette_id,
            "formation_id": curriculum.formation_id,
            "maquette_annee_id": curriculum.annee_universitaire_id,
            "maquette_universite_id": curriculum.annee_universitaire.universite_id,
            "semestre_id": unit.semestre_id,
            "semestre_annee_id": semester.annee_universitaire_id,
            "semestre_universite_id": semester.annee_universitaire.universite_id,
        }
    canonical = json.dumps(dimensions, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return {"version": 1, "sha256": hashlib.sha256(canonical).hexdigest()}


def course_snapshot(course):
    if course is None:
        return None
    return {**course_summary(course), _FINGERPRINT: course_scope_fingerprint(course)}


def readable_course_snapshot(request, snapshot):
    if snapshot is None:
        return None
    if not isinstance(snapshot, dict) or type(snapshot.get("id")) is not int:
        return {"disponible": False}
    fingerprint = snapshot.get(_FINGERPRINT)
    if not isinstance(fingerprint, dict) or type(fingerprint.get("version")) is not int:
        return {"disponible": False}
    course = visible_project_courses(request, request.user).filter(pk=snapshot["id"]).first()
    if course is None or snapshot[_FINGERPRINT] != course_scope_fingerprint(course):
        return {"disponible": False}
    fields = (
        {"classe": ("id", "nom"), "matiere": ("id", "nom")}
        if apps.is_installed("apps.classes")
        else {"ecue": ("id", "code", "nom")}
    )
    try:
        context = {
            name: {field: snapshot["contexte"][name][field] for field in allowed} for name, allowed in fields.items()
        }
        if not isinstance(snapshot["nom"], str) or any(
            type(values["id"]) is not int
            or any(not isinstance(value, str) for field, value in values.items() if field != "id")
            for values in context.values()
        ):
            return {"disponible": False}
        return {"id": snapshot["id"], "nom": snapshot["nom"], "contexte": context, "disponible": True}
    except (KeyError, TypeError):
        return {"disponible": False}
