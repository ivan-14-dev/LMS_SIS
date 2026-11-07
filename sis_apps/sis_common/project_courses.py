"""Local course references; never provision a course or grant any access."""

import hashlib
import json
from types import SimpleNamespace

from django.apps import apps
from django.db.models import Exists, F, OuterRef, Q
from rest_framework.exceptions import PermissionDenied, ValidationError

from sis_common.authorization import filter_queryset_by_scopes
from sis_common.lms_tenants import current_lms_tenant
from sis_common.pagination import SISPagination

COURSE_PERMISSION = "integration.view_edxcoursemapping"
_FINGERPRINT = "_scope_fingerprint"


class ProjectCoursePagination(SISPagination):
    page_size = 20
    max_page_size = 50


def visible_project_courses(request, user):
    from apps.integration.api import visible_course_mappings
    from apps.integration.models import EdxCourseMapping

    empty = EdxCourseMapping.objects.none()
    if not user.is_active or user.etablissement_id != request.tenant.pk or not user.has_perm(COURSE_PERMISSION):
        return empty
    attributes = user.attributs_acces
    if attributes is None:
        attributes = {}
    permission_scopes = attributes.get("permission_scopes", {}) if isinstance(attributes, dict) else None
    scopes = permission_scopes.get(COURSE_PERMISSION, {}) if isinstance(permission_scopes, dict) else None
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
    context = SimpleNamespace(tenant=request.tenant, user=user)
    try:
        if user.is_staff:
            # Preserve the administrative boundary; teacher assignments cannot extend it.
            return visible_course_mappings(context).filter(actif=True)
        current_lms_tenant(context)
        return _assigned_project_courses(context)
    except PermissionDenied:
        return empty


def _assigned_project_courses(request):
    from apps.integration.models import EdxCourseMapping
    from apps.portail.api import _TenantTeacherPortal

    user, tenant_id = request.user, request.tenant.pk
    secondary = apps.is_installed("apps.classes")
    roles = ("enseignant",) if secondary else ("enseignant", "chercheur")
    profile_model = apps.get_model("enseignants", "Personnel" if secondary else "EnseignantChercheur")
    teacher = profile_model.objects.filter(user_id=user.pk, user__etablissement_id=tenant_id).first()
    if user.role not in roles or teacher is None:
        return EdxCourseMapping.objects.none()
    # Reuse only the portal's local queryset; never delegate an endpoint or promote the user.
    portal = _TenantTeacherPortal()
    portal.request = request
    assignments = portal._affectations_queryset(teacher)
    if secondary:
        # Match the same assignment's class, subject AND year, not separate grants.
        assignments = assignments.filter(
            classes__pk=OuterRef("classe_id"),
            matiere_id=OuterRef("matiere_id"),
            annee_scolaire_id=OuterRef("classe__annee_scolaire_id"),
        )
        courses = EdxCourseMapping.objects.filter(
            actif=True,
            classe__etablissement_id=tenant_id,
            classe__niveau__etablissement_id=tenant_id,
            classe__annee_scolaire__etablissement_id=tenant_id,
            matiere__etablissement_id=tenant_id,
        )
        scope_fields = {"cours": "pk", "classes": "classe_id", "matieres": "matiere_id"}
        years = ("classe__annee_scolaire_id",)
    else:
        # An ECUE assignment never grants its siblings; a UE-only assignment does.
        assignments = assignments.filter(
            Q(ecue_id=OuterRef("ecue_id")) | Q(ecue__isnull=True, ue_id=OuterRef("ecue__ue_id")),
            Q(ue__isnull=True) | Q(ecue__isnull=True) | Q(ue_id=F("ecue__ue_id")),
            annee_universitaire_id=OuterRef("ecue__ue__maquette__annee_universitaire_id"),
        )
        courses = EdxCourseMapping.objects.filter(
            actif=True,
            ecue__ue__semestre__annee_universitaire__universite_id=tenant_id,
            ecue__ue__maquette__annee_universitaire__universite_id=tenant_id,
        )
        scope_fields = {"cours": "pk", "ecues": "ecue_id", "formations": "ecue__ue__maquette__formation_id"}
        years = ("ecue__ue__semestre__annee_universitaire_id", "ecue__ue__maquette__annee_universitaire_id")
    courses = courses.filter(Exists(assignments))
    for year in years:
        courses = filter_queryset_by_scopes(courses, user, COURSE_PERMISSION, {**scope_fields, "annees": year})
    return courses.select_related(*(("classe", "matiere") if secondary else ("ecue",))).order_by("course_name", "pk")


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
