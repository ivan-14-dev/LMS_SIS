"""Explicit, tenant-local research permissions shared by academic and finance APIs."""

from django.contrib.auth import get_user_model
from django.db import connection
from django.db.models import F, Q
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError
from rest_framework.permissions import BasePermission

from sis_common.module_registry import require_module

from .models import Laboratoire, ProductionScientifique, ProjetRecherche, These

MANAGE = "recherche.gerer_recherche"
CONSULT = "recherche.consulter_recherche"
CONTRIBUTE = "recherche.contribuer_recherche"
FINANCE = "recherche.comptabiliser_recherche"
SCOPE_FIELDS = {"etablissement_id", "laboratoire_id", "projet_id"}
ACTIVE_STUDENTS = ("inscrit", "redoublant")


class ResearchConflict(APIException):
    status_code = 409
    default_detail = "Version périmée ou état incompatible. Rechargez les données."
    default_code = "research_conflict"


def current_research_user(request):
    if request is None or not getattr(getattr(request, "user", None), "is_authenticated", False):
        return None
    tenant = getattr(request, "tenant", None)
    if (
        tenant is None or getattr(connection, "schema_name", None) != tenant.schema_name
        or request.user.etablissement_id != tenant.pk
    ):
        return None
    if not type(tenant).objects.filter(pk=tenant.pk, actif=True).exists():
        return None
    user = get_user_model().objects.filter(
        pk=request.user.pk, etablissement_id=tenant.pk, is_active=True,
    ).first()
    if user is None:
        return None
    try:
        require_module(tenant, "sis.research")
    except PermissionDenied:
        return None
    return user


class ResearchAccess(BasePermission):
    def has_permission(self, request, view):
        return current_research_user(request) is not None


def constraints_for(user, permission):
    if user is None:
        return None
    if user.is_superuser:
        return {}
    if not user.has_perm(permission):
        return None
    attributes = user.attributs_acces
    if not isinstance(attributes, dict):
        return None
    scopes = attributes.get("permission_scopes", {})
    if not isinstance(scopes, dict):
        return None
    constraints = scopes.get(permission, {})
    if not isinstance(constraints, dict):
        return None
    for key, values in constraints.items():
        if key not in SCOPE_FIELDS or not isinstance(values, list) or not values:
            return None
        if any(type(value) is not int or value <= 0 for value in values):
            return None
    return constraints


def local_laboratories(request):
    if request is None or getattr(request, "tenant", None) is None:
        return Laboratoire.objects.none()
    tenant_id = request.tenant.pk
    return Laboratoire.objects.filter(
        Q(faculte__isnull=True) | Q(faculte__universite_id=tenant_id),
        Q(directeur__isnull=True) | Q(directeur__user__etablissement_id=tenant_id),
        Q(faculte__doyen__isnull=True) | Q(faculte__doyen__etablissement_id=tenant_id),
    )


def local_projects(request):
    if request is None or getattr(request, "tenant", None) is None:
        return ProjetRecherche.objects.none()
    tenant_id = request.tenant.pk
    foreign_members = get_user_model().objects.exclude(etablissement_id=tenant_id)
    return ProjetRecherche.objects.filter(
        laboratoire__in=local_laboratories(request),
        responsable__user__etablissement_id=tenant_id,
    ).exclude(membres__user__in=foreign_members)


def local_theses(request):
    if request is None or getattr(request, "tenant", None) is None:
        return These.objects.none()
    tenant_id = request.tenant.pk
    return These.objects.filter(
        Q(co_directeur__isnull=True) | Q(co_directeur__user__etablissement_id=tenant_id),
        Q(projet__isnull=True) | Q(
            projet__in=local_projects(request), projet__laboratoire_id=F("laboratoire_id"),
        ),
        laboratoire__in=local_laboratories(request),
        doctorant__universite_id=tenant_id, doctorant__user__etablissement_id=tenant_id,
        directeur__user__etablissement_id=tenant_id,
    )


def scoped_projects(request, user, permission):
    constraints = constraints_for(user, permission)
    queryset = local_projects(request)
    if constraints is None:
        return queryset.none()
    for key, values in constraints.items():
        if key == "etablissement_id":
            if request.tenant.pk not in values:
                return queryset.none()
        else:
            queryset = queryset.filter(**{f"{'pk' if key == 'projet_id' else key}__in": values})
    return queryset


def member_projects(request, user):
    supervised = local_theses(request).filter(
        Q(doctorant__user_id=user.pk) | Q(directeur__user_id=user.pk) | Q(co_directeur__user_id=user.pk),
        archive=False, statut="en_cours", doctorant__user__is_active=True,
        doctorant__statut__in=ACTIVE_STUDENTS, projet__isnull=False,
    )
    if hasattr(user, "etudiant_profile"):
        return local_projects(request).filter(
            pk__in=supervised.filter(doctorant__user_id=user.pk).values("projet_id"),
        )
    return local_projects(request).filter(
        Q(responsable__user_id=user.pk) | Q(membres__user_id=user.pk)
        | Q(pk__in=supervised.values("projet_id")),
    ).distinct()


def allowed(request, permission, *, laboratoire=None, projet=None):
    user = current_research_user(request)
    if user is None:
        return False
    constraints = constraints_for(user, permission)
    if constraints is None:
        return False
    context = {"etablissement_id": request.tenant.pk}
    if projet is not None:
        if not local_projects(request).filter(pk=projet.pk).exists():
            return False
        if laboratoire is not None and laboratoire.pk != projet.laboratoire_id:
            return False
        context.update(projet_id=projet.pk, laboratoire_id=projet.laboratoire_id)
    elif laboratoire is not None:
        if not local_laboratories(request).filter(pk=laboratoire.pk).exists():
            return False
        context["laboratoire_id"] = laboratoire.pk
    if any(context.get(key) not in values for key, values in constraints.items()):
        return False
    if permission in (CONSULT, CONTRIBUTE):
        return projet is not None and member_projects(request, user).filter(pk=projet.pk).exists()
    return True


def academic_projects(request):
    user = current_research_user(request)
    if user is None:
        return ProjetRecherche.objects.none()
    members = member_projects(request, user)
    permitted = scoped_projects(request, user, MANAGE)
    for permission in (CONSULT, CONTRIBUTE):
        permitted = permitted | scoped_projects(request, user, permission).filter(pk__in=members.values("pk"))
    return permitted.distinct()


def visible_projects(request):
    user = current_research_user(request)
    if user is None:
        return ProjetRecherche.objects.none()
    return (academic_projects(request) | scoped_projects(request, user, FINANCE).distinct()).distinct()


def can_read_academic(request, projet):
    return allowed(request, MANAGE, projet=projet) or any(
        allowed(request, permission, projet=projet) for permission in (CONSULT, CONTRIBUTE)
    )


def can_contribute(request, projet):
    return allowed(request, MANAGE, projet=projet) or allowed(request, CONTRIBUTE, projet=projet)


def managed_laboratories(request):
    user = current_research_user(request)
    queryset = local_laboratories(request)
    if user is None:
        return queryset.none()
    constraints = constraints_for(user, MANAGE)
    if constraints is None or "projet_id" in constraints:
        return queryset.none()
    if "etablissement_id" in constraints and request.tenant.pk not in constraints["etablissement_id"]:
        return queryset.none()
    if "laboratoire_id" in constraints:
        queryset = queryset.filter(pk__in=constraints["laboratoire_id"])
    return queryset


def visible_laboratories(request):
    return local_laboratories(request).filter(
        Q(pk__in=managed_laboratories(request).values("pk"))
        | Q(pk__in=visible_projects(request).values("laboratoire_id")),
    )


def visible_productions(request):
    if request is None or getattr(request, "tenant", None) is None:
        return ProductionScientifique.objects.none()
    base = ProductionScientifique.objects.filter(laboratoire__in=local_laboratories(request))
    foreign_users = get_user_model().objects.exclude(etablissement_id=request.tenant.pk)
    base = base.exclude(auteurs__user__in=foreign_users)
    user = current_research_user(request)
    if user is None:
        return base.none()
    return base.filter(
        Q(projet__isnull=True, laboratoire__in=managed_laboratories(request))
        | Q(projet__in=scoped_projects(request, user, MANAGE), projet__laboratoire_id=F("laboratoire_id"))
        | Q(
            projet__in=academic_projects(request), statut="publiee", archive=False,
            projet__laboratoire_id=F("laboratoire_id"),
        ),
    ).distinct()


def visible_theses(request):
    user = current_research_user(request)
    queryset = local_theses(request)
    if user is None:
        return queryset.none()
    managers = Q(projet__in=scoped_projects(request, user, MANAGE)) | Q(
        projet__isnull=True, laboratoire__in=managed_laboratories(request),
    )
    readers = Q(projet__in=academic_projects(request))
    # Student membership never permits reading another student's doctoral dossier.
    if hasattr(user, "etudiant_profile"):
        readers &= Q(doctorant__user_id=user.pk, archive=False, statut="en_cours")
    return queryset.filter(managers | readers).distinct()


def check_version(instance, version):
    if type(version) is not int or version < 1:
        raise ValidationError({"version": "Une version entière positive est requise."})
    if instance.version != version:
        raise ResearchConflict()
